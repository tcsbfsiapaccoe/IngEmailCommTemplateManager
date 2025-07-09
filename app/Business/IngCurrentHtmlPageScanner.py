import os
from typing import List
from bs4 import BeautifulSoup, Tag

class IngCurrentHtmlPageScanner:
    def get_html_page_TR_tags(self, current_html_page_path : str) -> List[Tag]:
        """
        Extracts all <tr> tags from the given HTML page's table[1] and table[2] (which are used for main sections
        and footer sections respectively).

        :param current_html_page_path: Path to the HTML page.
        :return: List of <tr> tags.
        """
        if not os.path.exists(current_html_page_path):
            print(f"Error: HTML file not found at '{current_html_page_path}'")
            return []

        try:
            with open(current_html_page_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            print(f"Error reading HTML file: {e}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')

        table1_selector = 'html > body > div > center > div > table:nth-of-type(1)'
        table2_selector = 'html > body > div > center > div > table:nth-of-type(2)'

        table1 = soup.select_one(table1_selector)
        table2 = soup.select_one(table2_selector)

        all_tr_elements: List[Tag] = []

        if table1:
            tr_elements_table1 = table1.find_all('tr', recursive=False)
            all_tr_elements.extend(tr_elements_table1)
        else:
            print(f"Warning: Table matching selector '{table1_selector}' not found.")

        if table2:
            tr_elements_table2 = table2.find_all('tr', recursive=False)
            all_tr_elements.extend(tr_elements_table2)
        else:
            print(f"Warning: Table matching selector '{table2_selector}' not found.")

        non_empty_tr_elements: List[Tag] = [
            tr for tr in all_tr_elements if tr.get_text(strip=True) != ""
        ]

        return non_empty_tr_elements