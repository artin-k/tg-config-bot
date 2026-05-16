from aiogram.fsm.state import State, StatesGroup


class VerificationStates(StatesGroup):
    waiting_contact = State()


class WalletStates(StatesGroup):
    waiting_topup_amount = State()
    waiting_topup_receipt = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_destination_number = State()
    waiting_withdraw_account_holder = State()
    waiting_withdraw_note = State()
