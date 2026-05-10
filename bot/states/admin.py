from aiogram.fsm.state import State, StatesGroup


class AdminAddPlanStates(StatesGroup):
    title = State()
    duration_days = State()
    volume_gb = State()
    price = State()
