from Xlib import X, display as _display
import Xlib.protocol.event as _event

_NET_WM_STATE_ADD = 1


def set_desktop_widget_states(winid):
    d = _display.Display()
    try:
        root = d.screen().root
        win = d.create_resource_object("window", winid)
        net_wm_state = d.intern_atom("_NET_WM_STATE")
        states = [
            d.intern_atom("_NET_WM_STATE_SKIP_TASKBAR"),
            d.intern_atom("_NET_WM_STATE_SKIP_PAGER"),
        ]
        for i in range(0, len(states), 2):
            pair = states[i:i + 2]
            second = pair[1] if len(pair) > 1 else 0
            data = [_NET_WM_STATE_ADD, pair[0], second, 1, 0]
            ev = _event.ClientMessage(window=win, client_type=net_wm_state, data=(32, data))
            root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        d.flush()
    finally:
        d.close()
