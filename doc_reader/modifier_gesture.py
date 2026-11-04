"""Side-specific modifier routing, independent of the Windows hook/API.

Defer a reserved modifier's OS key-down until it becomes a chord. A bare tap
never reaches the OS (so Right Windows does not open Start). Ordinary chords
receive a matched synthetic down/up pair. Injected events bypass this state.
"""
from __future__ import annotations


class ModifierGesture:
    def __init__(self, key: int):
        self.key = key
        self.down = False
        self.forwarded = False
        self.canceled = False

    def event(self, key: int, down: bool, *, other_held: bool = False):
        """Return (suppress_original, [(virtual_key, down)], gesture).

        gesture is start/release/tap/cancel or empty. Callers dispatch only
        lightweight UI signals from their hook, never capture or network work.
        """
        if key == self.key:
            if down:
                if self.down:
                    return True, [], ""
                self.down = True
                self.canceled = other_held
                self.forwarded = other_held
                return True, [(key, True)] if other_held else [], "" if other_held else "start"
            if not self.down:
                return False, [], ""
            forwarded, canceled = self.forwarded, self.canceled
            self.down = self.forwarded = self.canceled = False
            return True, [(key, False)] if forwarded else [], "release" if canceled else "tap"
        if self.down and down and not self.canceled:
            self.canceled = self.forwarded = True
            return False, [(self.key, True)], "cancel"
        return False, [], ""
