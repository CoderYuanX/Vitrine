import inspect

from manager.runtime import WidgetRuntime


def test_runtime_accepts_task_bridge_param():
    sig = inspect.signature(WidgetRuntime.__init__)
    assert "task_bridge" in sig.parameters


def test_runtime_sets_tasks_context_property():
    src = inspect.getsource(WidgetRuntime.show_widget)
    assert 'setContextProperty("tasks"' in src


def test_app_constructs_and_passes_task_bridge():
    import manager.app as app_mod
    src = inspect.getsource(app_mod)
    assert "TaskBridge" in src
    assert "task_bridge" in src
