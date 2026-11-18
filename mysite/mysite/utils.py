# Utility functions that can be used in all apps

class UncertainValue:
    def __init__(self, min_val, max_val=None):
        """
        Initialize an UncertainValue.

        Can be created in two ways:
        1. With a single value (certain): UncertainValue(5)
        2. With min and max (uncertain): UncertainValue(3, 7)
        """
        self.min = min_val
        self.max = max_val if max_val is not None else min_val
        if self.min > self.max:
            raise ValueError("min_val must be less than or equal to max_val")

    @property
    def is_uncertain(self):
        """Return True if the value is uncertain (has a range)"""
        return self.min != self.max

    @property
    def value(self):
        """Return the deterministic value, or a tuple if uncertain."""
        return self.min if self.is_uncertain else (self.min, self.max)

    @property
    def mean(self):
        """Return the mean value"""
        return (self.min + self.max) / 2.0

    def __repr__(self):
        if self.is_uncertain:
            return f"{self.min} - {self.max}"
        return str(self.min)

    def __tuple__(self):
        return (self.min, self.max)

    def __iter__(self):
        yield self.min
        if self.is_uncertain:
            yield self.max

    def __float__(self):
        return self.mean

    def __add__(self, other):
        if isinstance(other, (int, float)):
            if self.is_uncertain:
                return UncertainValue(self.min + other, self.max + other)
            return UncertainValue(self.min + other)
        elif isinstance(other, UncertainValue):
            new_min = self.min + other.min
            new_max = self.max + other.max
            return UncertainValue(new_min, new_max)
        else:
            return NotImplemented

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            if self.is_uncertain:
                return UncertainValue(self.min - other, self.max - other)
            return UncertainValue(self.min - other)
        elif isinstance(other, UncertainValue):
            new_min = self.min - other.max
            new_max = self.max - other.min
            return UncertainValue(new_min, new_max)
        else:
            return NotImplemented

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            if self.is_uncertain:
                return UncertainValue(self.min * other, self.max * other)
            return UncertainValue(self.min * other)
        elif isinstance(other, UncertainValue):
            # For multiplication of two uncertain values, we need to consider all combinations
            products = [
                self.min * other.min, self.min * other.max,
                self.max * other.min, self.max * other.max,
            ]
            return UncertainValue(min(products), max(products))
        else:
            return NotImplemented

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Cannot divide by zero")
            # For negative divisors, we need to swap min and max
            elif other < 0:
                return UncertainValue(self.max / other, self.min / other)
            return UncertainValue(self.min / other, self.max / other)
        elif isinstance(other, UncertainValue):
            if other.min <= 0 <= other.max:
                return UncertainValue(float('-inf'), float('inf'))
            # Calculate all possible combinations
            results = [
                self.min / other.min, self.min / other.max,
                self.max / other.min, self.max / other.max,
            ]
            return UncertainValue(min_val=min(results), max_val=max(results))
        else:
            return NotImplemented

    def __radd__(self, other):
        return self.__add__(other)

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            return (
                UncertainValue(other - self.max, other - self.min)
                if self.is_uncertain
                else UncertainValue(other - self.min)
            )
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __rtruediv__(self, other):
        if isinstance(other, (int, float)):
            if other.min <= 0 <= other.max:
                return UncertainValue(float('-inf'), float('inf'))
            # Calculate all possible combinations
            results = [other / self.min, other / self.max]
            return UncertainValue(min(results), max(results))
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, UncertainValue):
            return (self.min == other.min) and (self.max == other.max)
        return False
