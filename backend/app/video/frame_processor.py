class FrameProcessor:
    """Hook for per-frame preprocessing that runs before detection.

    Currently a pass-through. Future steps (denoising, masking regions,
    colour correction, ...) belong here so the demo loop doesn't change.
    """

    def process(self, frame):
        """Return the (possibly modified) frame."""
        return frame