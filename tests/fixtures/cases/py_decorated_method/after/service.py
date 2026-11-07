import functools


class PriceService:
    def __init__(self, rates):
        self.rates = rates

    @functools.lru_cache(maxsize=128)
    def convert(self, amount, currency):
        if currency not in self.rates:
            return None
        return round(amount * self.rates[currency], 2)
