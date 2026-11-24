from uuid import UUID

from app.core.errors import Conflict, NotFound
from app.modules.bills.models import Bill
from app.modules.bills.repository import BillRepository
from app.modules.bills.schemas import BillInput, PayInput
from app.modules.budget.models import Expense
from app.modules.categories.service import CategoryService
from app.modules.recurrence.service import RecurrenceService


class BillService:
    def __init__(
        self,
        repository: BillRepository,
        categories: CategoryService,
        recurrence: RecurrenceService | None = None,
    ):
        self.repository = repository
        self.categories = categories
        self.recurrence = recurrence
        owners = {repository.user_id, categories.repository.user_id}
        if recurrence:
            owners.add(recurrence.repository.user_id)
        if len(owners) != 1:
            raise ValueError("Bill services must use the same authenticated owner.")

    def list(self, offset: int, limit: int, status: bool | None):
        if self.recurrence:
            self.recurrence.ensure()
        return self.repository.list(offset, limit, status)

    def get(self, record_id: UUID):
        record = self.repository.get(record_id)
        if record is None or record.user_id != self.repository.user_id:
            raise NotFound("This record could not be found.")
        return record

    def create(self, data: BillInput):
        return self.repository.save(Bill(user_id=self.repository.user_id, **data.model_dump()))

    def update(self, record_id: UUID, data: BillInput):
        """Edit only this bill. For a repeating bill, later occurrences are unchanged."""
        record = self.get(record_id)
        if record.paid and not data.paid and record.expense_id is not None:
            raise Conflict(
                "This payment was recorded as an expense. Delete that expense first "
                "so spending is not counted for an unpaid bill."
            )
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return self.repository.save(record)

    def pay(self, record_id: UUID, data: PayInput):
        """Mark a bill paid, optionally recording the payment as one linked expense.

        Repeating the request is safe: an already-linked bill never gets a second expense.
        No money is moved; this only records what the user reports.
        """
        bill = self.get(record_id)
        expense = None
        if data.record_expense and bill.expense_id is None and bill.amount > 0:
            self.categories.require("expense", data.category_id)
            expense = Expense(
                user_id=self.repository.user_id,
                amount=bill.amount,
                currency=bill.currency,
                category_id=data.category_id,
                spent_on=data.paid_on,
                note=data.note or bill.name,
                bill_id=bill.id,
            )
        if not self.repository.pay(bill, expense):
            bill = self.get(record_id)
            if not bill.paid:
                self.repository.pay(bill, None)
        return self.get(record_id)

    def delete(self, record_id: UUID):
        """Delete this bill only. A linked expense stays as recorded spending."""
        self.repository.delete(self.get(record_id))
