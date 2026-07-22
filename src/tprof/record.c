#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pythread.h>

#include <math.h>
#include <stdint.h>
#include <string.h>

/*
 * Recorded times are stored in C data structures rather than Python objects,
 * to minimize per-call overhead and memory use:
 *
 * - Each thread has its own ThreadData struct, found via thread-specific
 *   storage (TSS), holding a stack of enter times and an array of call
 *   durations per target, all as raw int64_t nanosecond values. No locking
 *   is needed in the event callbacks.
 * - Target code objects are stored in a small C array and matched by pointer
 *   comparison, instead of hashing (code, thread id) tuples into a dict.
 *   Value-equal code objects count as the same target, matching dict
 *   behaviour - for example, re-running a module with runpy recompiles code
 *   objects equal to those resolved from the initial import. Each thread
 *   caches the code pointers it has matched so the equality check runs at
 *   most once per (thread, code object).
 * - On Python 3.13+, timestamps come from PyTime_PerfCounterRaw(), avoiding
 *   a Python-level call to time.perf_counter_ns() and int boxing/unboxing.
 *
 * stats() computes the reported statistics directly over the raw values,
 * so recorded times never need converting to Python ints at all - only the
 * six aggregate values per target cross into Python.
 *
 * ThreadData structs live in a linked list until the module is freed.
 * configure() bumps a generation counter; each thread lazily resets its
 * ThreadData when it next records an event, and stats() only reads data
 * from the current generation. This avoids freeing memory that another
 * thread's in-flight callback might still be using.
 */

typedef struct {
    int64_t *items;
    Py_ssize_t len;
    Py_ssize_t capacity;
} I64Array;

typedef struct ThreadData {
    struct ThreadData *next;
    uint64_t generation;
    Py_ssize_t num_targets;
    PyObject **codes;       /* per target, last matched code object (strong) */
    I64Array *enter_stacks; /* per target, a stack of start times */
    I64Array *durations;    /* per target, elapsed times of completed calls */
} ThreadData;

typedef struct {
    PyObject **codes; /* strong references to target code objects */
    Py_ssize_t num_targets;
    uint64_t generation;
    Py_tss_t tss;
    int tss_created;
    ThreadData *threads; /* linked list of every thread's data */
    PyThread_type_lock threads_lock;
    PyObject *monitoring_disable; /* sys.monitoring.DISABLE */
#if PY_VERSION_HEX < 0x030D0000
    PyObject *perf_counter_ns;
#endif
} RecordModuleState;

static inline RecordModuleState *
get_module_state(PyObject *module)
{
    void *state = PyModule_GetState(module);
    assert(state != NULL);
    return (RecordModuleState *)state;
}

static int
now_ns(RecordModuleState *state, int64_t *result)
{
#if PY_VERSION_HEX >= 0x030D0000
    PyTime_t timestamp;
    (void)state;
    if (PyTime_PerfCounterRaw(&timestamp) < 0) {
        PyErr_SetString(PyExc_OSError, "failed to read performance counter");
        return -1;
    }
    *result = (int64_t)timestamp;
    return 0;
#else
    PyObject *timestamp = PyObject_CallNoArgs(state->perf_counter_ns);
    if (timestamp == NULL) {
        return -1;
    }
    long long value = PyLong_AsLongLong(timestamp);
    Py_DECREF(timestamp);
    if (value == -1 && PyErr_Occurred()) {
        return -1;
    }
    *result = (int64_t)value;
    return 0;
#endif
}

static int
i64array_append(I64Array *array, int64_t value)
{
    if (array->len == array->capacity) {
        Py_ssize_t new_capacity = array->capacity ? array->capacity * 2 : 64;
        int64_t *new_items =
            PyMem_RawRealloc(array->items, (size_t)new_capacity * sizeof(int64_t));
        if (new_items == NULL) {
            PyErr_NoMemory();
            return -1;
        }
        array->items = new_items;
        array->capacity = new_capacity;
    }
    array->items[array->len++] = value;
    return 0;
}

static void
thread_data_free_arrays(ThreadData *data)
{
    for (Py_ssize_t i = 0; i < data->num_targets; i++) {
        Py_DECREF(data->codes[i]);
        PyMem_RawFree(data->enter_stacks[i].items);
        PyMem_RawFree(data->durations[i].items);
    }
    PyMem_RawFree(data->codes);
    PyMem_RawFree(data->enter_stacks);
    PyMem_RawFree(data->durations);
    data->codes = NULL;
    data->enter_stacks = NULL;
    data->durations = NULL;
    data->num_targets = 0;
}

static ThreadData *
get_thread_data(RecordModuleState *state)
{
    ThreadData *data = (ThreadData *)PyThread_tss_get(&state->tss);
    if (data == NULL) {
        data = PyMem_RawCalloc(1, sizeof(ThreadData));
        if (data == NULL) {
            PyErr_NoMemory();
            return NULL;
        }
        if (PyThread_tss_set(&state->tss, data) != 0) {
            PyMem_RawFree(data);
            PyErr_SetString(PyExc_RuntimeError, "failed to set thread-specific storage");
            return NULL;
        }
        PyThread_acquire_lock(state->threads_lock, 1);
        data->next = state->threads;
        state->threads = data;
        PyThread_release_lock(state->threads_lock);
    }
    if (data->generation != state->generation) {
        thread_data_free_arrays(data);
        Py_ssize_t num_targets = state->num_targets;
        if (num_targets > 0) {
            data->codes = PyMem_RawCalloc((size_t)num_targets, sizeof(PyObject *));
            data->enter_stacks = PyMem_RawCalloc((size_t)num_targets, sizeof(I64Array));
            data->durations = PyMem_RawCalloc((size_t)num_targets, sizeof(I64Array));
            if (data->codes == NULL || data->enter_stacks == NULL || data->durations == NULL) {
                PyMem_RawFree(data->codes);
                PyMem_RawFree(data->enter_stacks);
                PyMem_RawFree(data->durations);
                data->codes = NULL;
                data->enter_stacks = NULL;
                data->durations = NULL;
                PyErr_NoMemory();
                return NULL;
            }
            for (Py_ssize_t i = 0; i < num_targets; i++) {
                data->codes[i] = Py_NewRef(state->codes[i]);
            }
            data->num_targets = num_targets;
        }
        data->generation = state->generation;
    }
    return data;
}

/* Returns the target index for the given code object, -1 for a non-target,
   or -2 if an error occurred. */
static Py_ssize_t
find_target(ThreadData *data, PyObject *code)
{
    for (Py_ssize_t i = 0; i < data->num_targets; i++) {
        if (data->codes[i] == code) {
            return i;
        }
    }
    for (Py_ssize_t i = 0; i < data->num_targets; i++) {
        int equal = PyObject_RichCompareBool(data->codes[i], code, Py_EQ);
        if (equal < 0) {
            return -2;
        }
        if (equal) {
            Py_INCREF(code);
            Py_SETREF(data->codes[i], code);
            return i;
        }
    }
    return -1;
}

static PyObject *
py_start_callback(PyObject *module, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "py_start_callback requires exactly 2 arguments");
        return NULL;
    }

    RecordModuleState *state = get_module_state(module);

    ThreadData *data = get_thread_data(state);
    if (data == NULL) {
        return NULL;
    }

    Py_ssize_t index = find_target(data, args[0]);
    if (index == -2) {
        return NULL;
    }
    if (index == -1) {
        /* Not a target: stop PY_START events firing for this code location. */
        return Py_NewRef(state->monitoring_disable);
    }

    int64_t timestamp;
    if (now_ns(state, &timestamp) < 0) {
        return NULL;
    }
    if (i64array_append(&data->enter_stacks[index], timestamp) < 0) {
        return NULL;
    }

    Py_RETURN_NONE;
}

static PyObject *
py_end_common(
    PyObject *module, PyObject *const *args, Py_ssize_t nargs, PyObject *non_target_result)
{
    if (nargs != 3) {
        PyErr_SetString(PyExc_TypeError, "py_end callbacks require exactly 3 arguments");
        return NULL;
    }

    RecordModuleState *state = get_module_state(module);

    ThreadData *data = get_thread_data(state);
    if (data == NULL) {
        return NULL;
    }

    Py_ssize_t index = find_target(data, args[0]);
    if (index == -2) {
        return NULL;
    }
    if (index == -1) {
        return Py_NewRef(non_target_result);
    }

    int64_t end_time;
    if (now_ns(state, &end_time) < 0) {
        return NULL;
    }

    I64Array *enter_stack = &data->enter_stacks[index];
    if (enter_stack->len == 0) {
        /* No matching PY_START, e.g. profiling started mid-call. */
        Py_RETURN_NONE;
    }
    int64_t start_time = enter_stack->items[--enter_stack->len];

    if (i64array_append(&data->durations[index], end_time - start_time) < 0) {
        return NULL;
    }

    Py_RETURN_NONE;
}

static PyObject *
py_return_callback(PyObject *module, PyObject *const *args, Py_ssize_t nargs)
{
    RecordModuleState *state = get_module_state(module);
    /* Not a target: stop PY_RETURN events firing for this code location. */
    return py_end_common(module, args, nargs, state->monitoring_disable);
}

static PyObject *
py_unwind_callback(PyObject *module, PyObject *const *args, Py_ssize_t nargs)
{
    /* PY_UNWIND events cannot be disabled, so return None for non-targets. */
    return py_end_common(module, args, nargs, Py_None);
}

static PyObject *
record_configure(PyObject *module, PyObject *arg)
{
    if (!PyTuple_Check(arg)) {
        PyErr_SetString(PyExc_TypeError, "configure() argument must be a tuple");
        return NULL;
    }

    RecordModuleState *state = get_module_state(module);

    Py_ssize_t num_targets = PyTuple_GET_SIZE(arg);
    PyObject **codes = NULL;
    if (num_targets > 0) {
        codes = PyMem_RawCalloc((size_t)num_targets, sizeof(PyObject *));
        if (codes == NULL) {
            return PyErr_NoMemory();
        }
        for (Py_ssize_t i = 0; i < num_targets; i++) {
            PyObject *code = PyTuple_GET_ITEM(arg, i);
            if (!PyCode_Check(code)) {
                for (Py_ssize_t j = 0; j < i; j++) {
                    Py_DECREF(codes[j]);
                }
                PyMem_RawFree(codes);
                PyErr_SetString(
                    PyExc_TypeError, "configure() argument must contain only code objects");
                return NULL;
            }
            codes[i] = Py_NewRef(code);
        }
    }

    for (Py_ssize_t i = 0; i < state->num_targets; i++) {
        Py_DECREF(state->codes[i]);
    }
    PyMem_RawFree(state->codes);
    state->codes = codes;
    state->num_targets = num_targets;
    state->generation++;

    /* Eagerly reset this thread's data, freeing the previous session's
       storage. Other threads reset their own data lazily on their next
       recorded event. */
    ThreadData *data = (ThreadData *)PyThread_tss_get(&state->tss);
    if (data != NULL && data->generation != state->generation) {
        thread_data_free_arrays(data);
        data->generation = state->generation - 1;
    }

    Py_RETURN_NONE;
}

/* Partially sort values so values[k] holds the k'th smallest value, with all
   smaller values before it, using quickselect with Hoare partitioning. */
static int64_t
select_kth(int64_t *values, Py_ssize_t length, Py_ssize_t k)
{
    Py_ssize_t low = 0;
    Py_ssize_t high = length - 1;
    while (low < high) {
        int64_t pivot = values[low + (high - low) / 2];
        Py_ssize_t i = low - 1;
        Py_ssize_t j = high + 1;
        for (;;) {
            do {
                i++;
            } while (values[i] < pivot);
            do {
                j--;
            } while (values[j] > pivot);
            if (i >= j) {
                break;
            }
            int64_t swapped = values[i];
            values[i] = values[j];
            values[j] = swapped;
        }
        if (k <= j) {
            high = j;
        }
        else {
            low = j + 1;
        }
    }
    return values[k];
}

static PyObject *
record_stats(PyObject *module, PyObject *Py_UNUSED(ignored))
{
    RecordModuleState *state = get_module_state(module);

    /* Snapshot the list head; nodes are only prepended, and only freed when
       the module is freed, so iterating without the lock is safe. */
    PyThread_acquire_lock(state->threads_lock, 1);
    ThreadData *threads = state->threads;
    PyThread_release_lock(state->threads_lock);

    PyObject *result = PyList_New(state->num_targets);
    if (result == NULL) {
        return NULL;
    }

    for (Py_ssize_t i = 0; i < state->num_targets; i++) {
        Py_ssize_t count = 0;
        for (ThreadData *data = threads; data != NULL; data = data->next) {
            if (data->generation == state->generation) {
                count += data->durations[i].len;
            }
        }

        /* Gather this target's durations from the per-thread buffers into
           one scratch buffer, for the median's quickselect. */
        int64_t *values = NULL;
        if (count > 0) {
            values = PyMem_RawMalloc((size_t)count * sizeof(int64_t));
            if (values == NULL) {
                Py_DECREF(result);
                return PyErr_NoMemory();
            }
            Py_ssize_t position = 0;
            for (ThreadData *data = threads; data != NULL; data = data->next) {
                if (data->generation != state->generation) {
                    continue;
                }
                I64Array *durations = &data->durations[i];
                if (durations->len > 0) {
                    memcpy(&values[position],
                        durations->items,
                        (size_t)durations->len * sizeof(int64_t));
                    position += durations->len;
                }
            }
        }

        int64_t total = 0;
        int64_t minimum = 0;
        int64_t maximum = 0;
        for (Py_ssize_t j = 0; j < count; j++) {
            int64_t value = values[j];
            if (j == 0 || value < minimum) {
                minimum = value;
            }
            if (j == 0 || value > maximum) {
                maximum = value;
            }
            total += value;
        }

        /* Sample standard deviation, matching statistics.stdev(). */
        double stdev = 0.0;
        if (count > 1) {
            double mean = (double)total / (double)count;
            double squared_deviations = 0.0;
            for (Py_ssize_t j = 0; j < count; j++) {
                double deviation = (double)values[j] - mean;
                squared_deviations += deviation * deviation;
            }
            stdev = sqrt(squared_deviations / (double)(count - 1));
        }

        /* Median, matching statistics.median(): for an even count, the
           midpoint of the two middle values. Computed last since quickselect
           reorders the scratch buffer. */
        double median = 0.0;
        if (count > 0) {
            int64_t upper = select_kth(values, count, count / 2);
            if (count % 2) {
                median = (double)upper;
            }
            else {
                int64_t lower = values[0];
                for (Py_ssize_t j = 1; j < count / 2; j++) {
                    if (values[j] > lower) {
                        lower = values[j];
                    }
                }
                median = ((double)lower + (double)upper) / 2.0;
            }
        }

        PyMem_RawFree(values);

        PyObject *item = Py_BuildValue("nLLLdd",
            count,
            (long long)total,
            (long long)minimum,
            (long long)maximum,
            median,
            stdev);
        if (item == NULL) {
            Py_DECREF(result);
            return NULL;
        }
        PyList_SET_ITEM(result, i, item);
    }

    return result;
}

static PyMethodDef record_methods[] = {
    {"configure", (PyCFunction)record_configure, METH_O, NULL},
    {"stats", (PyCFunction)record_stats, METH_NOARGS, NULL},
    {"py_start_callback", (PyCFunction)py_start_callback, METH_FASTCALL, NULL},
    {"py_return_callback", (PyCFunction)py_return_callback, METH_FASTCALL, NULL},
    {"py_unwind_callback", (PyCFunction)py_unwind_callback, METH_FASTCALL, NULL},
    {NULL, NULL, 0, NULL}};

static int
record_exec(PyObject *module)
{
    RecordModuleState *state = get_module_state(module);
    state->codes = NULL;
    state->num_targets = 0;
    state->generation = 0;
    state->tss_created = 0;
    state->threads = NULL;
    state->threads_lock = NULL;
    state->monitoring_disable = NULL;
#if PY_VERSION_HEX < 0x030D0000
    state->perf_counter_ns = NULL;
#endif

    state->threads_lock = PyThread_allocate_lock();
    if (state->threads_lock == NULL) {
        PyErr_NoMemory();
        return -1;
    }

    if (PyThread_tss_create(&state->tss) != 0) {
        PyErr_SetString(PyExc_RuntimeError, "failed to create thread-specific storage");
        return -1;
    }
    state->tss_created = 1;

    PyObject *sys_module = PyImport_ImportModule("sys");
    if (sys_module == NULL) {
        return -1;
    }
    PyObject *monitoring = PyObject_GetAttrString(sys_module, "monitoring");
    Py_DECREF(sys_module);
    if (monitoring == NULL) {
        return -1;
    }
    state->monitoring_disable = PyObject_GetAttrString(monitoring, "DISABLE");
    Py_DECREF(monitoring);
    if (state->monitoring_disable == NULL) {
        return -1;
    }

#if PY_VERSION_HEX < 0x030D0000
    PyObject *time_module = PyImport_ImportModule("time");
    if (time_module == NULL) {
        return -1;
    }
    state->perf_counter_ns = PyObject_GetAttrString(time_module, "perf_counter_ns");
    Py_DECREF(time_module);
    if (state->perf_counter_ns == NULL) {
        return -1;
    }
#endif

    return 0;
}

static int
record_traverse(PyObject *module, visitproc visit, void *arg)
{
    RecordModuleState *state = get_module_state(module);
    for (Py_ssize_t i = 0; i < state->num_targets; i++) {
        Py_VISIT(state->codes[i]);
    }
    Py_VISIT(state->monitoring_disable);
#if PY_VERSION_HEX < 0x030D0000
    Py_VISIT(state->perf_counter_ns);
#endif
    return 0;
}

static int
record_clear(PyObject *module)
{
    RecordModuleState *state = get_module_state(module);
    for (Py_ssize_t i = 0; i < state->num_targets; i++) {
        Py_CLEAR(state->codes[i]);
    }
    PyMem_RawFree(state->codes);
    state->codes = NULL;
    state->num_targets = 0;
    Py_CLEAR(state->monitoring_disable);
#if PY_VERSION_HEX < 0x030D0000
    Py_CLEAR(state->perf_counter_ns);
#endif
    return 0;
}

static void
record_free(void *module)
{
    RecordModuleState *state = get_module_state((PyObject *)module);
    (void)record_clear((PyObject *)module);

    ThreadData *data = state->threads;
    while (data != NULL) {
        ThreadData *next = data->next;
        thread_data_free_arrays(data);
        PyMem_RawFree(data);
        data = next;
    }
    state->threads = NULL;

    if (state->tss_created) {
        PyThread_tss_delete(&state->tss);
        state->tss_created = 0;
    }
    if (state->threads_lock != NULL) {
        PyThread_free_lock(state->threads_lock);
        state->threads_lock = NULL;
    }
}

static PyModuleDef_Slot record_slots[] = {{Py_mod_exec, record_exec},
#ifdef Py_GIL_DISABLED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}};

PyDoc_STRVAR(module_doc, "tprof recording module");

static struct PyModuleDef record_module_def = {
    PyModuleDef_HEAD_INIT,
    .m_name = "tprof.record",
    .m_doc = module_doc,
    .m_size = sizeof(RecordModuleState),
    .m_methods = record_methods,
    .m_slots = record_slots,
    .m_traverse = record_traverse,
    .m_clear = record_clear,
    .m_free = record_free,
};

PyMODINIT_FUNC
PyInit_record(void)
{
    return PyModuleDef_Init(&record_module_def);
}
