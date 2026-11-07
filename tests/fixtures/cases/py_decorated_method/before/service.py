import functools


class PriceService:
    def __init__(self, rates):
        self.rates = rates

    @functools.lru_cache(maxsize=128)
    def convert(self, amount, currency):
        return amount * self.rates[currency]
