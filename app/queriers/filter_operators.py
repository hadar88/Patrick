from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any


class FilterOperator(ABC):
    @abstractmethod
    def apply(self, statement: Any, column: Any, values: Any) -> Any:
        pass


class EqualsFilterOperator(FilterOperator):
    def apply(self, statement: Any, column: Any, values: Iterable[object]) -> Any:
        return statement.where(column.in_(list(values)))


class RangeFilterOperator(FilterOperator):
    def apply(
        self,
        statement: Any,
        column: Any,
        values: tuple[object, object],
    ) -> Any:
        from_value, to_value = values
        return statement.where(column >= from_value, column <= to_value)


FILTER_OPERATORS: dict[str, FilterOperator] = {
    "EQUALS": EqualsFilterOperator(),
    "RANGE": RangeFilterOperator(),
}
