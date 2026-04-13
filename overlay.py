#!/usr/bin/env python3
"""
overlay.py – Floating status-pill overlay for whisper-dictate.

Shows a small pill at the top-centre of the screen:
  • Red  + "Recording…"     while the hotkey is held
  • Dark + "Transcribing…"  while faster-whisper processes audio
  • Hidden                  at all other times

Requires pyobjc-framework-Cocoa.  If the package is missing the module
still imports cleanly — the Overlay class becomes a silent no-op so
dictate.py works exactly as before.
"""

import math
import signal
import sys
import threading

# ------------------------------------------------------------------
# Graceful degradation: everything still works without PyObjC.
# ------------------------------------------------------------------
try:
    import objc          # type: ignore
    import AppKit        # type: ignore
    _HAS_APPKIT = True
except ImportError:
    _HAS_APPKIT = False

# States (plain ints — safe to read/write across threads under the GIL)
HIDDEN = 0
RECORDING = 1
TRANSCRIBING = 2

# Geometry
_W = 180        # pill width
_H = 36         # pill height
_R = 18         # corner radius  (= _H/2 → perfect capsule)
_TOP = 60       # px from the top of the screen


# ── PyObjC implementation ────────────────────────────────────────
if _HAS_APPKIT:

    class _PillView(AppKit.NSView):
        """Draws the rounded pill with a pulsing dot and a label."""

        def initWithFrame_(self, frame):
            self = objc.super(_PillView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._state = HIDDEN
            self._pulse = 1.0
            return self

        # noinspection PyMethodMayBeStatic
        def isFlipped(self):
            return False

        def drawRect_(self, dirty):                         # noqa: N802
            if self._state == HIDDEN:
                return

            bounds = self.bounds()
            pill = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                bounds, _R, _R,
            )

            # ── background ──────────────────────────────────
            if self._state == RECORDING:
                AppKit.NSColor.colorWithRed_green_blue_alpha_(
                    0.82, 0.08, 0.08, 0.92,
                ).setFill()
            else:
                AppKit.NSColor.colorWithRed_green_blue_alpha_(
                    0.13, 0.13, 0.15, 0.92,
                ).setFill()
            pill.fill()

            # ── pulsing indicator dot ───────────────────────
            ds = 10
            dy = (_H - ds) / 2.0
            dot = AppKit.NSBezierPath.bezierPathWithOvalInRect_(
                AppKit.NSMakeRect(14, dy, ds, ds),
            )
            if self._state == RECORDING:
                AppKit.NSColor.colorWithRed_green_blue_alpha_(
                    1.0, 0.40, 0.40, self._pulse,
                ).setFill()
            else:
                AppKit.NSColor.colorWithRed_green_blue_alpha_(
                    0.40, 0.72, 1.0, self._pulse,
                ).setFill()
            dot.fill()

            # ── text label ──────────────────────────────────
            label = (
                "Recording\u2026"
                if self._state == RECORDING
                else "Transcribing\u2026"
            )
            attrs = {
                AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_weight_(
                    13, 0.3,
                ),
                AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor(),
            }
            astr = AppKit.NSAttributedString.alloc().initWithString_attributes_(
                label, attrs,
            )
            astr.drawInRect_(AppKit.NSMakeRect(30, (_H - 16) / 2.0, _W - 40, 18))

    # NSTimer needs a genuine ObjC target object.
    class _Tick(AppKit.NSObject):

        def initWithOverlay_(self, ov):                     # noqa: N802
            self = objc.super(_Tick, self).init()
            if self is None:
                return None
            self._ov = ov
            return self

        def fire_(self, timer):                             # noqa: N802
            self._ov._tick()

    class Overlay:
        """Thread-safe floating pill driven by NSApplication's run loop."""

        def __init__(self):
            self._state = HIDDEN          # any thread may write
            self._n = 0
            self._window = None
            self._view = None

        # -- public, thread-safe ------------------------------------

        def show_recording(self):
            self._state = RECORDING

        def show_transcribing(self):
            self._state = TRANSCRIBING

        def hide(self):
            self._state = HIDDEN

        # -- main-thread entry point --------------------------------

        def run(self, on_ready):
            """
            Build the overlay UI, fire *on_ready* in a daemon thread,
            then block on ``NSApp.run()``.

            Must be called on the **main thread**.
            """
            try:
                self._setup()
            except Exception as exc:
                print(
                    f"[overlay] Could not start overlay: {exc}",
                    file=sys.stderr,
                )
                # Fall back to headless operation.
                on_ready()
                return

            # Fire the caller's "ready" hook in a background thread.
            threading.Thread(target=on_ready, daemon=True).start()

            app = AppKit.NSApplication.sharedApplication()
            app.run()      # blocks until terminated

        # -- internals (main thread only) ---------------------------

        def _setup(self):
            app = AppKit.NSApplication.sharedApplication()
            app.setActivationPolicy_(
                AppKit.NSApplicationActivationPolicyAccessory,
            )

            screen = AppKit.NSScreen.mainScreen()
            sw = screen.frame().size.width
            sh = screen.frame().size.height

            frame = AppKit.NSMakeRect(
                (sw - _W) / 2.0, sh - _TOP - _H, _W, _H,
            )

            win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                frame,
                AppKit.NSWindowStyleMaskBorderless,
                AppKit.NSBackingStoreBuffered,
                False,
            )
            win.setLevel_(25)           # NSStatusWindowLevel
            win.setOpaque_(False)
            win.setBackgroundColor_(AppKit.NSColor.clearColor())
            win.setIgnoresMouseEvents_(True)
            win.setHasShadow_(True)
            win.setCollectionBehavior_(1 | 16)   # allSpaces | stationary

            self._window = win

            self._view = _PillView.alloc().initWithFrame_(
                AppKit.NSMakeRect(0, 0, _W, _H),
            )
            win.setContentView_(self._view)

            # 30-fps poll timer
            target = _Tick.alloc().initWithOverlay_(self)
            AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / 30.0, target, b"fire:", None, True,
            )

            # Ctrl-C / SIGTERM → clean exit
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: app.terminate_(None))

        def _tick(self):
            """Called ~30 fps on the main thread by the timer."""
            s = self._state
            self._n += 1
            self._view._pulse = 0.40 + 0.60 * abs(math.sin(self._n * 0.09))

            if s != self._view._state:
                self._view._state = s
                if s == HIDDEN:
                    self._window.orderOut_(None)
                else:
                    self._window.orderFront_(None)

            if s != HIDDEN:
                self._view.setNeedsDisplay_(True)


# ── Fallback (no PyObjC) ─────────────────────────────────────────
else:

    class Overlay:                          # type: ignore[no-redef]
        """Silent stand-in when pyobjc-framework-Cocoa is missing."""

        def show_recording(self):
            pass

        def show_transcribing(self):
            pass

        def hide(self):
            pass

        def run(self, on_ready):
            on_ready()      # just run the callback on the current thread
