#define PY_SSIZE_T_CLEAN
#include <Python.h>

typedef struct {
    PyObject *code_to_name;
    PyObject *enter_times;
    PyObject *call_times;
    PyObject *perf_counter_ns;
} RecordModuleState;

static inline RecordModuleState *
get_module_state(PyObject *module)
{
    void *state = PyModule_GetState(module);
    assert(state != NULL);
    return (RecordModuleState *)state;
}

static PyObject *
py_start_callback(PyObject *module, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "py_start_callback requires exactly 2 arguments");
        return NULL;
    }

    PyObject *code = args[0];
    RecordModuleState *state = get_module_state(module);

    PyObject *times_list = PyDict_GetItemWithError(state->enter_times, code);
    if (times_list == NULL) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        Py_RETURN_NONE;
    }

    PyObject *timestamp = PyObject_CallNoArgs(state->perf_counter_ns);
    if (timestamp == NULL) {
        return NULL;
    }

    int result = PyList_Append(times_list, timestamp);
    Py_DECREF(timestamp);
    if (result < 0) {
        return NULL;
    }

    Py_RETURN_NONE;
}

static PyObject *
py_end_callback(PyObject *module, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != 3) {
        PyErr_SetString(PyExc_TypeError, "py_end_callback requires exactly 3 arguments");
        return NULL;
    }

    PyObject *code = args[0];
    RecordModuleState *state = get_module_state(module);

    PyObject *times_list = PyDict_GetItemWithError(state->enter_times, code);
    if (times_list == NULL) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        Py_RETURN_NONE;
    }

    Py_ssize_t list_len = PyList_Size(times_list);
    if (list_len <= 0) {
        if (list_len < 0) {
            return NULL;
        }
        Py_RETURN_NONE;
    }

    PyObject *enter_time = PyList_GetItem(times_list, list_len - 1);
    if (enter_time == NULL) {
        return NULL;
    }
    Py_INCREF(enter_time);

    if (PyList_SetSlice(times_list, list_len - 1, list_len, NULL) < 0) {
        Py_DECREF(enter_time);
        return NULL;
    }

    PyObject *current_time = PyObject_CallNoArgs(state->perf_counter_ns);
    if (current_time == NULL) {
        Py_DECREF(enter_time);
        return NULL;
    }

    PyObject *duration = PyNumber_Subtract(current_time, enter_time);
    Py_DECREF(current_time);
    Py_DECREF(enter_time);
    if (duration == NULL) {
        return NULL;
    }

    PyObject *call_times_list = PyDict_GetItemWithError(state->call_times, code);
    if (call_times_list == NULL) {
        Py_DECREF(duration);
        if (PyErr_Occurred()) {
            return NULL;
        }
        Py_RETURN_NONE;
    }

    int result = PyList_Append(call_times_list, duration);
    Py_DECREF(duration);
    if (result < 0) {
        return NULL;
    }

    Py_RETURN_NONE;
}

static PyMethodDef record_methods[] = {
    {"py_start_callback", (PyCFunction)py_start_callback, METH_FASTCALL, NULL},
    {"py_end_callback", (PyCFunction)py_end_callback, METH_FASTCALL, NULL},
    {NULL, NULL, 0, NULL}};

static int
record_exec(PyObject *module)
{
    RecordModuleState *state = get_module_state(module);

    PyObject *time_module = PyImport_ImportModule("time");
    if (time_module == NULL) {
        goto error;
    }

    state->perf_counter_ns = PyObject_GetAttrString(time_module, "perf_counter_ns");
    Py_DECREF(time_module);
    if (state->perf_counter_ns == NULL) {
        goto error;
    }

    PyObject *api_module = PyImport_ImportModule("tprof.api");
    if (api_module == NULL) {
        goto error;
    }

    state->code_to_name = PyObject_GetAttrString(api_module, "code_to_name");
    if (state->code_to_name == NULL) {
        Py_DECREF(api_module);
        goto error;
    }

    state->enter_times = PyObject_GetAttrString(api_module, "enter_times");
    if (state->enter_times == NULL) {
        Py_DECREF(api_module);
        goto error;
    }

    state->call_times = PyObject_GetAttrString(api_module, "call_times");
    if (state->call_times == NULL) {
        Py_DECREF(api_module);
        goto error;
    }

    Py_DECREF(api_module);
    return 0;

error:
    Py_CLEAR(state->code_to_name);
    Py_CLEAR(state->enter_times);
    Py_CLEAR(state->call_times);
    Py_CLEAR(state->perf_counter_ns);
    return -1;
}

static int
record_traverse(PyObject *module, visitproc visit, void *arg)
{
    RecordModuleState *state = get_module_state(module);
    Py_VISIT(state->code_to_name);
    Py_VISIT(state->enter_times);
    Py_VISIT(state->call_times);
    Py_VISIT(state->perf_counter_ns);
    return 0;
}

static int
record_clear(PyObject *module)
{
    RecordModuleState *state = get_module_state(module);
    Py_CLEAR(state->code_to_name);
    Py_CLEAR(state->enter_times);
    Py_CLEAR(state->call_times);
    Py_CLEAR(state->perf_counter_ns);
    return 0;
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
};

PyMODINIT_FUNC
PyInit_record(void)
{
    return PyModuleDef_Init(&record_module_def);
}
