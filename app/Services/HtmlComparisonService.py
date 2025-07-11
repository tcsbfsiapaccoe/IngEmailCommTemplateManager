from typing import List, Dict, Union
from bs4 import Tag

from Business.HtmlSectionComparer import HtmlSectionComparer
from Entities.IngMasterTemplateGroup import IngMasterTemplateGroup
from Entities.IngMasterTemplate import IngMasterTemplate # Import to type hint

class HtmlComparisonService:
    """
    Service class responsible for orchestrating the comparison between current HTML TRs
    and master templates based on various criteria.
    """
    def __init__(self, comparer: HtmlSectionComparer):
        self._comparer = comparer

    def perform_comparison(
        self,
        current_html_trs: List[Tag],
        master_template_groups: List[IngMasterTemplateGroup],
        comparison_mode: str,
        min_similarity_cutoff: int,
        selected_template_group: str
    ) -> List[Dict[str, Union[Tag, List[Dict]]]]:
        """
        Compares each TR in the current HTML with all available master templates
        based on the specified comparison mode and filters.

        Args:
            current_html_trs (List[Tag]): A list of BeautifulSoup Tag objects
                                          representing <tr> elements from the current HTML.
            master_template_groups (List[IngMasterTemplateGroup]): A list of
                                                                    IngMasterTemplateGroup objects.
            comparison_mode (str): The mode of comparison ('text', 'structure', or 'both').
            min_similarity_cutoff (int): The minimum similarity percentage for a match.
            selected_template_group (str): The name of a specific template group to filter by,
                                           or an empty string to consider all groups.

        Returns:
            List[Dict[str, Union[Tag, List[Dict]]]]: A list where each item represents a
            current HTML TR and its best matching master templates.
            Example structure:
            [
                {
                    'current_tr': <Tag object for current TR>,
                    'matches': [
                        {
                            'master_template': <IngMasterTemplate object>,
                            'inner_text_score': float,
                            'structure_score': float,
                            'combined_score': float
                        },
                        ... sorted best to worst ...
                    ]
                },
                ...
            ]
        """
        results = []

        # Flatten all master templates from groups, applying group filter if specified
        all_master_templates: List[IngMasterTemplate] = []
        for group in master_template_groups:
            if not selected_template_group or group.template_group_name == selected_template_group:
                all_master_templates.extend(group.ing_master_templates)

        for current_tr in current_html_trs:
            tr_matches = []
            for master_template in all_master_templates:
                inner_text_score = 0.0
                structure_score = 0.0
                combined_score = 0.0

                # Perform comparisons based on mode
                if comparison_mode == 'text' or comparison_mode == 'both':
                    inner_text_score = self._comparer.compare_inner_text(current_tr, master_template.template_element)
                
                if comparison_mode == 'structure' or comparison_mode == 'both':
                    structure_score = self._comparer.compare_html_structure(current_tr, master_template.template_element)

                if comparison_mode == 'both':
                    # Simple average for combined score, can be weighted if needed
                    combined_score = (inner_text_score + structure_score) / 2
                elif comparison_mode == 'text':
                    combined_score = inner_text_score
                elif comparison_mode == 'structure':
                    combined_score = structure_score

                # Apply similarity cutoff
                if combined_score >= min_similarity_cutoff:
                    tr_matches.append({
                        'master_template': master_template,
                        'inner_text_score': inner_text_score,
                        'structure_score': structure_score,
                        'combined_score': combined_score
                    })
            
            # Sort matches by combined score in descending order
            tr_matches.sort(key=lambda x: x['combined_score'], reverse=True)
            
            results.append({
                'current_tr': current_tr,
                'matches': tr_matches
            })
        
        return results