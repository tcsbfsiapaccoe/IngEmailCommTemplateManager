from typing import List
from bs4 import Tag, Comment, NavigableString

from Entities.Tx import Tx
from Entities.DelimiterComment import DelimiterComment

class IngMasterTemplate:
    _template_name: str
    _delimiter: DelimiterComment
    _defining_elements: List[Tag | Comment | NavigableString]
    _template_element: Tag

    def __init__(self, template_name: str, delimiter_text: str, defining_elements: List[Tag | Comment | NavigableString]):
        if not template_name or template_name.isspace():
            raise ValueError("Template name cannot be null or whitespace.")

        self._template_name = template_name

        if not delimiter_text or delimiter_text.isspace():
            raise ValueError("Delimiter text cannot be null or whitespace.")

        self._delimiter = DelimiterComment(delimiter_text)

        if (
            defining_elements is None
            or len(defining_elements) != 3
            or not isinstance(defining_elements[0], Comment)
            or not isinstance(defining_elements[-1], Comment)
            or isinstance(defining_elements[1], Comment)
        ):
            raise ValueError("Defining elements must contain only START comment element, template element and END comment element.")

        self._defining_elements = defining_elements

        expected_start_comment_text = f"{delimiter_text}{Tx.START_SUFFIX}"
        actual_start_comment = defining_elements[0].string.strip()

        if actual_start_comment != expected_start_comment_text:
            raise ValueError(f"The first element must be a START comment with text '{expected_start_comment_text}'.")

        expected_end_comment_text = f"{delimiter_text}{Tx.END_SUFFIX}"
        actual_end_comment = defining_elements[-1].string.strip()

        if actual_end_comment != expected_end_comment_text:
            raise ValueError(f"The last element must be an END comment with text '{expected_end_comment_text}'.")

        if not isinstance(defining_elements[1], Tag):
            raise ValueError("The template element (middle element) must be a valid HTML tag.")
        self._template_element = defining_elements[1]

    @property
    def template_name(self) -> str:
        return self._template_name

    @property
    def delimiter(self) -> DelimiterComment:
        return self._delimiter

    @property
    def defining_elements(self) -> List[Tag | Comment | NavigableString]:
        return self._defining_elements

    @property
    def template_element(self) -> Tag:
        return self._template_element