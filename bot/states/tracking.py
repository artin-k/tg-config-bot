from aiogram.fsm.state import State, StatesGroup


class TrackingStates(StatesGroup):
    waiting_code = State()
