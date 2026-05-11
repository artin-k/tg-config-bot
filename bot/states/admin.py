from aiogram.fsm.state import State, StatesGroup


class AdminAddPlanStates(StatesGroup):
    title = State()
    description = State()
    duration_days = State()
    volume_gb = State()
    price = State()
    sort_order = State()
    confirm = State()


class AdminEditPlanStates(StatesGroup):
    value = State()
