from typing import List, Optional
from bs4 import Tag, Comment, NavigableString

from Entities.Tx import Tx
from Entities.DelimiterComment import DelimiterComment
from Entities.IngMasterTemplate import IngMasterTemplate

class IngMasterTemplateGroup:
    _GROUP_DELIMITER_TEXT = "TEMPLATE GROUP TITLE"

    _template_group_name: str
    _delimiter_comment: DelimiterComment
    _defining_elements: List[Tag | Comment | NavigableString]
    _ing_master_templates: List['IngMasterTemplate']

    def __init__(self, template_group_name: str, defining_elements: List[Tag | Comment | NavigableString], delimiter_text: Optional[str] = None):
        delimiter_text = delimiter_text if delimiter_text is not None else self._GROUP_DELIMITER_TEXT

        if not template_group_name or template_group_name.isspace():
            raise ValueError("Template group name cannot be null or whitespace.")

        if not delimiter_text or delimiter_text.isspace():
            raise ValueError("Delimiter text cannot be null or whitespace.")

        if defining_elements is None or len(defining_elements) == 0:
            raise ValueError("Defining elements cannot be null or empty.")

        self._template_group_name = template_group_name
        self._delimiter_comment = DelimiterComment(delimiter_text)
        self._defining_elements = defining_elements

        if (
            len(defining_elements) < 2
            or not isinstance(defining_elements[0], Comment)
            or not isinstance(defining_elements[-1], Comment)
            or isinstance(defining_elements[-2], Comment)
        ):
            raise ValueError("Defining elements for the group must start with a comment, end with a comment, and the element immediately preceding the end comment must not be a comment.")

        expected_start_comment_text = f"{delimiter_text}{Tx.START_SUFFIX}"
        actual_start_comment = defining_elements[0].string.strip()

        if actual_start_comment != expected_start_comment_text:
            raise ValueError(f"The first element for the group must be a START comment with text '{expected_start_comment_text}'.")

        expected_end_comment_text = f"{delimiter_text}{Tx.END_SUFFIX}"
        actual_end_comment = defining_elements[-1].string.strip()

        if actual_end_comment != expected_end_comment_text:
            raise ValueError(f"The last element for the group must be an END comment with text '{expected_end_comment_text}'.")

        self._ing_master_templates = []

    @property
    def template_group_name(self) -> str:
        return self._template_group_name

    @property
    def delimiter_comment(self) -> DelimiterComment:
        return self._delimiter_comment

    @property
    def defining_elements(self) -> List[Tag | Comment | NavigableString]:
        return self._defining_elements

    @property
    def ing_master_templates(self) -> List['IngMasterTemplate']:
        return self._ing_master_templates

    def add_ing_master_template(self, ing_master_template: 'IngMasterTemplate'):
        if ing_master_template is None:
            raise ValueError("IngMasterTemplate cannot be null.")

        self._ing_master_templates.append(ing_master_template)