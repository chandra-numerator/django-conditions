"""
:Created: 6 December 2014
:Author: Lucas Connors

"""

from django import forms
from django.db.models import JSONField
from django.forms import JSONField as JSONFormField
from django.forms import Textarea
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .conditions import CompareCondition
from .exceptions import InvalidConditionError
from .lists import CondList

__all__ = ["ConditionsWidget", "ConditionsFormField", "ConditionsField"]


class ConditionsWidget(Textarea):
    template_name = (
        "conditions/conditions_widget.html"  # Using the standard template_name
    )

    def __init__(self, *args, **kwargs):
        self.condition_definitions = kwargs.pop("condition_definitions", {})
        if "attrs" not in kwargs:
            kwargs["attrs"] = {}
        if "cols" not in kwargs["attrs"]:
            kwargs["attrs"]["cols"] = 50
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if isinstance(value, CondList):
            value = value.encode()

        condition_groups = []
        for groupname, group in self.condition_definitions.items():
            conditions_in_group = []
            for condstr, condition in group.items():
                conditions_in_group.append(
                    {
                        "condstr": condstr,
                        "key_required": "true" if condition.key_required() else "false",
                        "keys_allowed": condition.keys_allowed,
                        "key_example": condition.key_example(),
                        "operator_required": (
                            "true"
                            if issubclass(condition, CompareCondition)
                            else "false"
                        ),
                        "operators": (
                            condition.operators().keys()
                            if issubclass(condition, CompareCondition)
                            else []
                        ),
                        "operand_example": (
                            condition.operand_example()
                            if issubclass(condition, CompareCondition)
                            else ""
                        ),
                        "help_text": condition.help_text(),
                        "description": condition.full_description(),
                    }
                )
            conditions_in_group = sorted(
                conditions_in_group, key=lambda x: x["condstr"]
            )

            condition_groups.append(
                {
                    "groupname": groupname,
                    "conditions": conditions_in_group,
                }
            )
        condition_groups = sorted(condition_groups, key=lambda x: x["groupname"])

        context["condition_groups"] = condition_groups
        return context

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        return mark_safe(render_to_string(self.template_name, context))


class ConditionsFormField(JSONFormField):
    def __init__(self, *args, **kwargs):
        self.condition_definitions = kwargs.pop("condition_definitions", {})
        if "widget" not in kwargs:
            kwargs["widget"] = ConditionsWidget(
                condition_definitions=self.condition_definitions
            )
        super().__init__(*args, **kwargs)

    def clean(self, value):
        """Validate conditions by decoding result"""
        cleaned_json = super().clean(value)
        if cleaned_json is None:
            return

        try:
            CondList.decode(cleaned_json, definitions=self.condition_definitions)
        except InvalidConditionError as e:
            raise forms.ValidationError(
                "Invalid conditions JSON: {error}".format(error=str(e))
            )
        else:
            return cleaned_json


class ConditionsField(JSONField):
    """
    ConditionsField stores information on when the "value" of the
    instance should be considered True.
    """

    def __init__(self, *args, **kwargs):
        self.condition_definitions = kwargs.pop("definitions", {})
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        kwargs["condition_definitions"] = self.condition_definitions
        return ConditionsFormField(**kwargs)

    def pre_init(self, value, obj):
        value = super().pre_init(value, obj)
        if isinstance(value, dict):
            value = CondList.decode(value, definitions=self.condition_definitions)
        return value

    def dumps_for_display(self, value):
        if isinstance(value, CondList):
            value = value.encode()
        return super().dumps_for_display(value)

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, CondList):
            value = value.encode()
        return super().get_db_prep_value(value, connection, prepared)
