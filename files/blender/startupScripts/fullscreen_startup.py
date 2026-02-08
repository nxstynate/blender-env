import bpy


def force_fullscreen():
    # Don't run in background/CLI render mode
    if bpy.app.background:
        return None

    wm = bpy.context.window_manager

    for window in wm.windows:
        screen = window.screen
        if not screen.areas:
            continue

        # Pick a reasonable area to bind the context to
        # Prefer VIEW_3D, fall back to the first area
        area = next((a for a in screen.areas if a.type == "VIEW_3D"), screen.areas[0])

        # In 4.x, we must override context for operators that depend on window/area
        override = bpy.context.temp_override(window=window, screen=screen, area=area)

        with override:
            try:
                bpy.ops.wm.window_fullscreen_toggle()
            except RuntimeError:
                # Ignore if the operator can't run for some reason
                pass

    # Returning None stops the timer from repeating
    return None


# Register a timer so this runs *after* the UI has fully initialized
bpy.app.timers.register(force_fullscreen, first_interval=0.3)
