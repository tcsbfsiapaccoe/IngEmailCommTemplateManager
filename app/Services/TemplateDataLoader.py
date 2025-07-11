import os
from typing import List
from bs4 import BeautifulSoup, Tag, Comment, NavigableString

from Business.IngMasterTemplateScanner import IngMasterTemplateScanner
from Business.IngCurrentHtmlPageScanner import IngCurrentHtmlPageScanner
from Entities.IngMasterTemplateGroup import IngMasterTemplateGroup

class TemplateDataLoader:
    """
    Service class responsible for loading and preparing data from the master template
    and the current HTML page.
    """
    def __init__(self, master_template_scanner: IngMasterTemplateScanner,
                 current_html_page_scanner: IngCurrentHtmlPageScanner):
        self._master_template_scanner = master_template_scanner
        self._current_html_page_scanner = current_html_page_scanner

    def load_master_template_groups(self, master_template_html_path: str) -> List[IngMasterTemplateGroup]:
        """
        Loads and parses the master template HTML file to extract template groups.

        Args:
            master_template_html_path (str): The file path to the master template HTML.

        Returns:
            List[IngMasterTemplateGroup]: A list of parsed IngMasterTemplateGroup objects.

        Raises:
            FileNotFoundError: If the master template HTML file does not exist.
            Exception: For other parsing or data loading errors.
        """
        if not os.path.exists(master_template_html_path):
            raise FileNotFoundError(f"Master template HTML file not found: {master_template_html_path}")
        
        # The scanner handles the actual parsing and group extraction
        return self._master_template_scanner.get_template_groups(master_template_html_path)

    def load_current_html_trs(self, current_html_file_path: str) -> List[Tag]:
        """
        Loads and parses the current HTML file to extract all <tr> tags.

        Args:
            current_html_file_path (str): The file path to the current HTML page.

        Returns:
            List[Tag]: A list of BeautifulSoup Tag objects representing the <tr> elements.

        Raises:
            FileNotFoundError: If the current HTML file does not exist.
            Exception: For other parsing or data loading errors.
        """
        if not os.path.exists(current_html_file_path):
            raise FileNotFoundError(f"Current HTML file not found: {current_html_file_path}")

        # The scanner handles the actual parsing and TR extraction
        return self._current_html_page_scanner.get_html_page_TR_tags(current_html_file_path)