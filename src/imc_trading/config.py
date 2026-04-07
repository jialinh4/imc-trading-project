from datamodel import Listing
from .strategy.trader import Product

LISTINGS = {
    Product.AMETHYSTS: Listing(symbol=Product.AMETHYSTS, product=Product.AMETHYSTS, denomination="SEASHELLS"),
    Product.STARFRUIT: Listing(symbol=Product.STARFRUIT, product=Product.STARFRUIT, denomination="SEASHELLS"),
}

POSITION_LIMITS = {
    Product.AMETHYSTS: 20,
    Product.STARFRUIT: 20,
}
