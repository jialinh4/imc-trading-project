from datamodel import Order, TradingState


class Trader:
    def run(self, state: TradingState):
        orders = {}
        for product, depth in state.order_depths.items():
            if product == "EMERALDS" and depth.sell_orders:
                best_ask = min(depth.sell_orders)
                orders[product] = [Order(product, best_ask, 1)]
            else:
                orders[product] = []
        return orders, 0, state.traderData
