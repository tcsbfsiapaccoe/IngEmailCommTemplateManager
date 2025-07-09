import os
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup, Tag, Comment, NavigableString

from Entities.Tx import Tx
from Entities.IngMasterTemplate import IngMasterTemplate
from Entities.IngMasterTemplateGroup import IngMasterTemplateGroup

class IngMasterTemplateScanner:
    def get_template_groups(self, master_template_html_path: str) -> List[IngMasterTemplateGroup]:
        if not os.path.exists(master_template_html_path):
            raise FileNotFoundError(f"The specified master template HTML file does not exist: {master_template_html_path}")

        with open(master_template_html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        html_document = BeautifulSoup(html_content, 'html.parser')

        # Locate the table inside which the template groups and the templates are defined.
        target_table_one = html_document.select_one('html > body > div > center > div > table:nth-of-type(1)')
        template_groups_one = self._processMasterTemplateTable(target_table_one)

        target_table_two = html_document.select_one('html > body > div > center > div > table:nth-of-type(2)')
        template_groups_two = self._processMasterTemplateTable(target_table_two, spacer_block_present = False)

        return template_groups_one + template_groups_two

    def _processMasterTemplateTable (
        self,
        target_table_one: Tag,
        spacer_block_present: bool = True) -> List[IngMasterTemplateGroup]:
        
        if target_table_one is None:
            return []

        row_elements = target_table_one.contents

        if not row_elements:
            return []

        template_groups: List[IngMasterTemplateGroup] = []
        current_group: Optional[IngMasterTemplateGroup] = None
        current_defining_elements: List[Tag | Comment | NavigableString] = []

        start_delimiter_text: str = ""
        end_delimiter_text: str = ""
        template_group_name: str = ""
        next_template_name: str = ""

        template_spacer_starting_found: bool = False
        template_spacer_ending_found: bool = False
        time_to_read_template_instance: bool = False
        template_element_found: bool = False
        dummy_spacing_comment_found: bool = False
        new_group_is_starting: bool = False

        # Iterate through each node in the row elements
        for node in row_elements:
            if isinstance(node, NavigableString) and str(node).strip() == "":
                continue

            # Skip dummy spacing comments
            if isinstance(node, Comment) and Tx.DUMMY_SPACING in node.string.upper():
                dummy_spacing_comment_found = True
                continue

            # If a dummy spacing comment was found, skip the next <tr> element
            if dummy_spacing_comment_found and isinstance(node, Tag) and node.name == "tr":
                dummy_spacing_comment_found = False
                continue

            # Is it a "Template Group" starting comment?
            if isinstance(node, Comment) and f"{Tx.GROUP_DELIMITER_COMMENT_INDICATOR_TEXT}{Tx.START_SUFFIX}" in node.string:
                new_group_is_starting = True
                current_defining_elements = []

            if new_group_is_starting:
                # The control will reach inside this IF block multiple times until the end delimiter is found.
                (
                    current_group,
                    current_defining_elements,
                    start_delimiter_text,
                    end_delimiter_text,
                    template_group_name,
                    template_spacer_starting_found,
                    template_spacer_ending_found,
                    time_to_read_template_instance,
                    template_element_found,
                    new_group_is_starting
                ) = self._identify_template_group(
                    current_group,
                    current_defining_elements,
                    start_delimiter_text,
                    end_delimiter_text,
                    template_group_name,
                    template_spacer_starting_found,
                    template_spacer_ending_found,
                    time_to_read_template_instance,
                    template_element_found,
                    new_group_is_starting,
                    node
                )

                if current_group is not None and not new_group_is_starting:
                    current_defining_elements = []

            else:
                # New group is not starting, so we are reading the spacer block to read the next template details.
                if current_group is None:
                    continue

                if not time_to_read_template_instance and spacer_block_present:
                    # Control will reach here when the template spacer block is being read.
                    (
                        next_template_name,
                        template_spacer_starting_found,
                        template_spacer_ending_found,
                        time_to_read_template_instance,
                        continue_loop_flag
                    ) = self._read_next_template_details_from_spacer_block(
                        next_template_name,
                        template_spacer_starting_found,
                        template_spacer_ending_found,
                        time_to_read_template_instance,
                        node
                    )

                    if time_to_read_template_instance:
                        # The template spacer block END comment has been found.
                        # The next block to come will be the template element block.
                        current_defining_elements = []

                    if continue_loop_flag:
                        continue
                else:
                    # You are reading the template element block.
                    # Read the template element and add it to the current template group.
                    (
                        template_groups,
                        current_group,
                        current_defining_elements,
                        start_delimiter_text,
                        end_delimiter_text,
                        next_template_name,
                        template_spacer_starting_found,
                        template_spacer_ending_found,
                        time_to_read_template_instance,
                        template_element_found
                    ) = self._read_template_and_add_to_group(
                        template_groups,
                        current_group,
                        current_defining_elements,
                        start_delimiter_text,
                        end_delimiter_text,
                        next_template_name,
                        template_spacer_starting_found,
                        template_spacer_ending_found,
                        time_to_read_template_instance,
                        template_element_found,
                        node,
                        spacer_block_present
                    )

        return template_groups

    def _identify_template_group(
        self,
        current_group: Optional[IngMasterTemplateGroup],
        current_defining_elements: List[Tag | Comment | NavigableString],
        start_delimiter_text: str,
        end_delimiter_text: str,
        template_group_name: str,
        template_spacer_starting_found: bool,
        template_spacer_ending_found: bool,
        time_to_read_template_instance: bool,
        template_element_found: bool,
        new_group_is_starting: bool,
        node: Tag | Comment | NavigableString
    ) -> Tuple[Optional[IngMasterTemplateGroup], List[Tag | Comment | NavigableString], str, str, str, bool, bool, bool, bool, bool]:
        if isinstance(node, Comment):
            # Comment nodes around the template group.
            comment_text = node.string.strip()

            if comment_text == Tx.MARK_HEADERS:
                current_defining_elements.append(node)
            elif comment_text.endswith(Tx.START_SUFFIX):
                without_suffix = comment_text.replace(Tx.START_SUFFIX, "")
                if without_suffix == Tx.GROUP_DELIMITER_COMMENT_INDICATOR_TEXT:
                    start_delimiter_text = without_suffix
                    current_defining_elements.append(node)
            elif comment_text.endswith(Tx.END_SUFFIX):
                without_suffix = comment_text.replace(Tx.END_SUFFIX, "")
                if without_suffix == Tx.GROUP_DELIMITER_COMMENT_INDICATOR_TEXT:
                    end_delimiter_text = without_suffix
                    current_defining_elements.append(node)

        elif isinstance(node, Tag):
            # You have reached the single <tr> element that contains the template group name.
            # Reach the table inside, and read the template group name.
            if node.name == "tr":
                inner_table = node.find('td').find('table') if node.find('td') else None

                if inner_table:
                    template_group_name = inner_table.get_text(strip=True)

                    if template_group_name:
                        current_defining_elements.append(node)
        if (
            start_delimiter_text == end_delimiter_text
            and start_delimiter_text == Tx.GROUP_DELIMITER_COMMENT_INDICATOR_TEXT
            and template_group_name
        ):
            # All the required elements to create a new group are found.
            current_group = IngMasterTemplateGroup(
                template_group_name,
                current_defining_elements,
                start_delimiter_text
            )

            new_group_is_starting = False

            start_delimiter_text = ""
            end_delimiter_text = ""
            template_group_name = ""

            template_spacer_starting_found = False
            template_spacer_ending_found = False
            time_to_read_template_instance = False
            template_element_found = False

        return (
            current_group,
            current_defining_elements,
            start_delimiter_text,
            end_delimiter_text,
            template_group_name,
            template_spacer_starting_found,
            template_spacer_ending_found,
            time_to_read_template_instance,
            template_element_found,
            new_group_is_starting
        )

    def _read_next_template_details_from_spacer_block(
        self,
        next_template_name: str,
        template_spacer_starting_found: bool,
        template_spacer_ending_found: bool,
        time_to_read_template_instance: bool,
        node: Tag | Comment | NavigableString
    ) -> Tuple[str, bool, bool, bool, bool]:
        continue_loop_flag: bool = False

        if isinstance(node, Comment):
            comment_text = node.string.strip()

            if comment_text == f"{Tx.TEMPLATE_SPACER_COMMENT_INDICATOR_TEXT}{Tx.START_SUFFIX}":
                # You just found the template spacer starting comment.
                template_spacer_starting_found = True
                continue_loop_flag = True

                return (
                    next_template_name,
                    template_spacer_starting_found,
                    template_spacer_ending_found,
                    time_to_read_template_instance,
                    continue_loop_flag
                )

            if comment_text == f"{Tx.TEMPLATE_SPACER_COMMENT_INDICATOR_TEXT}{Tx.END_SUFFIX}":
                # You just found the template spacer ending comment.
                template_spacer_ending_found = True

        elif isinstance(node, Tag) and template_spacer_starting_found:
            # You are reading one of the three <tr> elements inside the template spacer block.
            if node.name == "tr":
                inner_text = node.get_text().replace("\xa0", "").strip()

                if not inner_text:
                    continue_loop_flag = True
                    
                    return (
                        next_template_name,
                        template_spacer_starting_found,
                        template_spacer_ending_found,
                        time_to_read_template_instance,
                        continue_loop_flag
                    )

                # You have found the next template name.
                next_template_name = inner_text

        # If both the template spacer starting and ending comments are found, and the next template name is not empty,
        # you're ready to read the template instance block coming up next.
        time_to_read_template_instance = (
            template_spacer_starting_found
            and template_spacer_ending_found
            and bool(next_template_name)
        )

        return (
            next_template_name,
            template_spacer_starting_found,
            template_spacer_ending_found,
            time_to_read_template_instance,
            continue_loop_flag
        )

    def _read_template_and_add_to_group(
        self,
        template_groups: List[IngMasterTemplateGroup],
        current_group: IngMasterTemplateGroup,
        current_defining_elements: List[Tag | Comment | NavigableString],
        start_delimiter_text: str,
        end_delimiter_text: str,
        next_template_name: str,
        template_spacer_starting_found: bool,
        template_spacer_ending_found: bool,
        time_to_read_template_instance: bool,
        template_element_found: bool,
        node: Tag | Comment | NavigableString,
        spacer_block_present: bool = True
    ) -> Tuple[List[IngMasterTemplateGroup], IngMasterTemplateGroup, List[Tag | Comment | NavigableString], str, str, str, bool, bool, bool, bool]:
        if isinstance(node, Comment):
            comment_text = node.string.strip()

            # Is it a template element starting or ending comment?
            if comment_text.endswith(Tx.START_SUFFIX):
                current_defining_elements = []
                start_delimiter_text = comment_text.replace(Tx.START_SUFFIX, "")
                
                if (spacer_block_present):
                    next_template_name = start_delimiter_text
                    
                current_defining_elements.append(node)
                
            elif comment_text.endswith(Tx.END_SUFFIX):
                end_delimiter_text = comment_text.replace(Tx.END_SUFFIX, "")
                current_defining_elements.append(node)

        elif isinstance(node, Tag):
            # Is it the single <tr> element that contains the template element?
            if node.name == "tr":
                template_element_found = True
                current_defining_elements.append(node)

        if (
            template_element_found
            and start_delimiter_text == end_delimiter_text
            and bool(start_delimiter_text)
        ):
            if (spacer_block_present == False and (not next_template_name or next_template_name == '')):
                next_template_name = start_delimiter_text
            
            # All the required elements to create a new template are found.
            template = IngMasterTemplate(
                next_template_name,
                start_delimiter_text,
                current_defining_elements
            )

            # Add the newly found template to the current template group.
            current_group.add_ing_master_template(template)

            # If the current template group is not already in the template groups list, add it.
            if current_group not in template_groups:
                template_groups.append(current_group)

            # Reset the variables for the next block (most likely, either a template spacer block or a template group block).
            start_delimiter_text = ""
            end_delimiter_text = ""
            next_template_name = ""

            template_element_found = False

            template_spacer_starting_found = False
            template_spacer_ending_found = False
            time_to_read_template_instance = False

        return (
            template_groups,
            current_group,
            current_defining_elements,
            start_delimiter_text,
            end_delimiter_text,
            next_template_name,
            template_spacer_starting_found,
            template_spacer_ending_found,
            time_to_read_template_instance,
            template_element_found
        )