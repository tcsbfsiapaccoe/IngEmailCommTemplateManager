from typing import List
from bs4 import Tag
from fuzzywuzzy import fuzz
import difflib

class HtmlSectionComparer:
    """
    A class to compare two <tr> Tag elements based on their inner text content and their HTML tag
    hierarchy. Comparison results are returned as a percentage (0.0 to 100.0).
    """

    def compare_inner_text(self, tr_tag_1: Tag, tr_tag_2: Tag) -> float:
        """
        Compares the inner text content of two <tr> tags and returns a similarity percentage.
        Uses FuzzyWuzzy's fuzz.ratio for string comparison.

        Args:
            tr_tag_1 (Tag): The first <tr> tag.
            tr_tag_2 (Tag): The second <tr> tag.

        Returns:
            float: A percentage (0.0 to 100.0) indicating the similarity of their inner texts.
                   Returns 100.0 if both are empty. Returns 0.0 if one is empty and the other is not.
        """

        text_1 = tr_tag_1.get_text(strip=True)
        text_2 = tr_tag_2.get_text(strip=True)

        if not text_1 and not text_2:
            return 100.0

        if not text_1 or not text_2:
            return 0.0

        score = fuzz.ratio(text_1, text_2)
        return float(score)

    def compare_tag_hierarchy(self, tr_tag_1: Tag, tr_tag_2: Tag) -> float:
        """
        Compares the HTML tag hierarchy (structure) within two <tr> tags and returns a similarity
        percentage. This is done by comparing the ordered sequence of tag names found within each <tr>.

        Args:
            tr_tag_1 (Tag): The first <tr> tag.
            tr_tag_2 (Tag): The second <tr> tag.

        Returns:
            float: A percentage (0.0 to 100.0) indicating the structural similarity.
                   Returns 100.0 if both have identical empty structures (e.g., <tr></tr>).
                   Returns 0.0 if one has structure and the other doesn't.
        """

        hierarchy_seq_1 = self._get_tag_name_sequence(tr_tag_1)
        hierarchy_seq_2 = self._get_tag_name_sequence(tr_tag_2)

        if not hierarchy_seq_1 and not hierarchy_seq_2:
            return 100.0

        if not hierarchy_seq_1 or not hierarchy_seq_2:
            return 0.0

        matcher = difflib.SequenceMatcher(None, hierarchy_seq_1, hierarchy_seq_2)
        score = matcher.ratio() * 100

        return float(score)
    
    def _get_tag_name_sequence(self, root_tag: Tag) -> List[str]:
        """
        Helps generate a flattened sequence of descendant tag names. This sequence represents the
        structural composition within the root_tag, preserving the order of appearance.
        """
        sequence = []
        
        for tag in root_tag.find_all(True):
            sequence.append(tag.name)

        return sequence