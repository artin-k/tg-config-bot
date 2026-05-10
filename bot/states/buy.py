from aiogram.fsm.state import State, StatesGroup


class BuyStates(StatesGroup):
    waiting_username = State()
    waiting_receipt = State()
