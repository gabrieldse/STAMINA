class Filter:
    def __init__(self, output_dir, bounds = None, pixel_size_m=1000):
        self.bounds = bounds
        self.output_dir = output_dir
        self.pixel_size_m = pixel_size_m
    def run(self):
        raise NotImplementedError("Subclasses should implement this!")