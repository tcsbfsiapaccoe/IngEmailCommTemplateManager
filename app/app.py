import os
import re
import shutil
import sys

from datetime import datetime

from typing import List, Dict, Optional, Union
from bs4 import Tag, BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for, flash

from Business.HtmlSectionComparer import HtmlSectionComparer
from Business.IngCurrentHtmlPageScanner import IngCurrentHtmlPageScanner
from Business.IngMasterTemplateScanner import IngMasterTemplateScanner

app = Flask(__name__)

# A strong, unique secret key is required for the flask to flash messages on the page.
app.secret_key = 'f3a1b5c9d7e0f2a4b6c8d0e1f3a5b7c9d1e2f4a6b8c0d2e4f6a8b9c1d3e5f7a9'

master_template_scanner = IngMasterTemplateScanner()
html_page_scanner = IngCurrentHtmlPageScanner()
comparer = HtmlSectionComparer()

comparison_results_data: List[Dict[str, Union[Tag, List[Dict]]]] = []

initial_backup_done = False

MASTER_TEMPLATE_HTML_PATH = r"C:\DEV\ING\IngEmailCommTemplateManager\HtmlFiles\MasterTemplate.html"
CURRENT_HTML_PAGE_PATH = r"C:\DEV\ING\IngEmailCommTemplateManager\HtmlFiles\120172_WelcometoOrange_masked.html"
# CURRENT_HTML_PAGE_PATH = r"C:\DEV\ING\IngEmailCommTemplateManager\HtmlFiles\8046_YourOrangeOneAC_Masked.html"
# CURRENT_HTML_PAGE_PATH = r"C:\DEV\ING\IngEmailCommTemplateManager\HtmlFiles\8053_YourOrangeOneha_masked.html"

def load_application_data():
    """
    Loads TR elements of both Master Template and Current HTML, and pre-calculates all comparison results.
    This function should be called once when the app starts.
    """
    global comparison_results_data
    global initial_backup_done

    template_groups = []

    try:
        template_groups = master_template_scanner.get_template_groups(MASTER_TEMPLATE_HTML_PATH)
    except FileNotFoundError as e:
        print(f"Error: Master template file not found at '{MASTER_TEMPLATE_HTML_PATH}'. Please ensure the file exists. Error: {e}", file=sys.stderr)
    except ValueError as e:
        print(f"Data validation error in master template: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred during master template loading: {e}", file=sys.stderr)

    # Flattens the loaded master template groups to extract all valid <tr> elements.
    all_master_template_trs_list: List[Tag] = [
        template.template_element
        for group in template_groups
        for template in group.ing_master_templates
        if template.template_element is not None
    ]

    print(f"Loaded {len(all_master_template_trs_list)} master template TRs.")

    current_html_page_section_tags: List[Tag] = []

    try:
        # Read the "<tr>" Content Section element tags from the current HTML file.
        current_html_page_section_tags = html_page_scanner.get_html_page_TR_tags(CURRENT_HTML_PAGE_PATH)
    except FileNotFoundError as e:
        print(f"Error: Current HTML page file not found at '{CURRENT_HTML_PAGE_PATH}'. Please ensure the file exists. Error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred during current HTML page loading: {e}", file=sys.stderr)
    print(f"Loaded {len(current_html_page_section_tags)} current HTML page TRs.")

    comparison_results_data = []

    if not all_master_template_trs_list:
        print("Warning: No master template TRs available. Cannot perform comparisons.", file=sys.stderr)

    for html_tr in current_html_page_section_tags:
        matches_for_current_tr = []

        if all_master_template_trs_list:
            for master_tr in all_master_template_trs_list:
                # Get the comparison scores for this <tr> tag against the Master Template <tr> tags.
                inner_text_score = comparer.compare_inner_text(html_tr, master_tr)
                tag_hierarchy_score = comparer.compare_tag_hierarchy(html_tr, master_tr)
                combined_score = (inner_text_score + tag_hierarchy_score) / 2

                # Add to the "matching <tr>s" collection.
                matches_for_current_tr.append({
                    'master_tr_tag': master_tr,
                    'text_score': inner_text_score,
                    'hierarchy_score': tag_hierarchy_score,
                    'combined_score': combined_score
                })

            # Sort the "matching <tr>s" collection by the combined score.
            matches_for_current_tr.sort(key=lambda x: x['combined_score'], reverse=True)

        # Prepare the current <tr> vs. matching <tr>s dictionary.
        comparison_results_data.append({
            'html_tr_tag': html_tr,
            'matches': matches_for_current_tr
        })

    print(f"Pre-calculated comparison results for {len(comparison_results_data)} HTML TRs.")

with app.app_context():
    # When the app starts, load the application data.
    load_application_data()

@app.route('/')
def home():
    return redirect(url_for('compare_trs', html_tr_index=0, match_index=0, comparison_mode='text', min_similarity_cutoff='50'))

@app.route('/compare')
def compare_trs():
    # Get the current option values from the request arguments.
    html_tr_index = request.args.get('html_tr_index', type=int, default=0)
    match_index = request.args.get('match_index', type=int, default=0)
    comparison_mode = request.args.get('comparison_mode', default='text')
    min_similarity_cutoff_str = request.args.get('min_similarity_cutoff', default='50')

    min_similarity_cutoff = int(min_similarity_cutoff_str)

    if not comparison_results_data:
        flash("No TRs found in the current HTML file for comparison. Please ensure the file exists and contains valid TR tags.", 'error')
        return render_template('index.html', error_message="No TRs found in the current HTML file for comparison. Please ensure the file exists and contains valid TR tags.")

    total_html_trs = len(comparison_results_data)

    if not (0 <= html_tr_index < total_html_trs):
        html_tr_index = 0

    # Get the HTML <tr> element for the index from the dictionary.
    current_html_tr_data = comparison_results_data[html_tr_index]
    one_tr_in_html_file = current_html_tr_data['html_tr_tag']

    # Get the corresponding best match, and other "less matching" Master Template <tr>s.
    raw_matches_for_current_tr = current_html_tr_data['matches']

    filtered_matches = []

    if raw_matches_for_current_tr:
        for match in raw_matches_for_current_tr:
            score_to_check = 0.0

            # Apply the selected comparison radio option ("text", "hierarchy", or "both").
            if comparison_mode == 'text':
                score_to_check = match['text_score']
            elif comparison_mode == 'hierarchy':
                score_to_check = match['hierarchy_score']
            else:
                score_to_check = match['combined_score']

            # Apply minimum comparison score cutoff, and add to
            # the matching Master Template <tr>s collection.
            if score_to_check >= min_similarity_cutoff:
                filtered_matches.append(match)

        # Apply the match score based sorting.
        if comparison_mode == 'text':
            filtered_matches.sort(key=lambda x: x['text_score'], reverse=True)
        elif comparison_mode == 'hierarchy':
            filtered_matches.sort(key=lambda x: x['hierarchy_score'], reverse=True)
        else:
            filtered_matches.sort(key=lambda x: x['combined_score'], reverse=True)

    matches_for_current_tr = filtered_matches

    # Initialize variables for template rendering
    master_tr_html_display: str = ""
    text_percentage_display: str = ""
    hierarchy_percentage_display: str = ""
    combined_percentage_display: str = ""
    prev_match_disabled: str = ""
    next_match_disabled: str = ""
    go_to_best_match_disabled: str = ""
    current_match_number: int = 0
    total_matches: int = 0
    apply_button_disabled_for_100_percent: str = ""

    if not matches_for_current_tr:
        # There are no matches. Display "No match found" message.
        master_tr_html_display = "<em>No matching master template TR found with the current criteria.</em>"
        text_percentage_display = "N/A"
        hierarchy_percentage_display = "N/A"
        combined_percentage_display = "N/A"

        # Disable all match navigation buttons
        prev_match_disabled = "disabled"
        next_match_disabled = "disabled"
        go_to_best_match_disabled = "disabled"
        current_match_number = 0
        total_matches = 0
        apply_button_disabled_for_100_percent = "disabled"
    else:
        # There are matching Template sections corresponding to the currently selected "Match options".
        total_matches = len(matches_for_current_tr)

        if not (0 <= match_index < total_matches):
            match_index = 0

        # Get the current matching Master Template <tr> tag (not necessarily the "best" unless match_index is 0).
        current_match_data = matches_for_current_tr[match_index]
        best_match_tr = current_match_data['master_tr_tag']

        # Embed the current matching Master Template <tr> tag into a <table> element for display.
        master_tr_html_display = f"<table><tbody><tr>{best_match_tr.decode_contents()}</tr></tbody></table>" if best_match_tr else "<em>Error: Master TR tag missing.</em>"

        # Write the comparison scores for the current match.
        best_inner_text_percentage = current_match_data['text_score']
        best_tag_hierarchy_percentage = current_match_data['hierarchy_score']
        best_combined_percentage = current_match_data['combined_score']

        text_percentage_display = f"{best_inner_text_percentage:.2f}%"
        hierarchy_percentage_display = f"{best_tag_hierarchy_percentage:.2f}%"
        combined_percentage_display = f"{best_combined_percentage:.2f}%"

        prev_match_disabled = "disabled" if match_index == 0 else ""
        next_match_disabled = "disabled" if match_index == total_matches - 1 else ""
        go_to_best_match_disabled = "disabled" if match_index == 0 else ""
        current_match_number = match_index + 1

        # Check for 100% match to disable apply button
        current_match_score = 0.0
        if comparison_mode == 'text':
            current_match_score = best_inner_text_percentage
        elif comparison_mode == 'hierarchy':
            current_match_score = best_tag_hierarchy_percentage
        else:
            current_match_score = best_combined_percentage

        if current_match_score >= 99.99:
            apply_button_disabled_for_100_percent = "disabled"
        else:
            apply_button_disabled_for_100_percent = ""

    # Embed the current HTML <tr> tag into a <table> element for display.
    current_tr_html_display = f"<table><tbody><tr>{one_tr_in_html_file.decode_contents()}</tr></tbody></table>"

    # Control access to the "Previous" and "Next" HTML TR navigation links.
    prev_html_tr_disabled = "disabled" if html_tr_index == 0 else ""
    next_html_tr_disabled = "disabled" if html_tr_index == total_html_trs - 1 else ""

    # You have all the details needed to render the index.html template.
    return render_template(
        'index.html',
        current_tr_html=current_tr_html_display,
        master_tr_html=master_tr_html_display,

        text_percentage=text_percentage_display,
        hierarchy_percentage=hierarchy_percentage_display,
        combined_percentage=combined_percentage_display,

        prev_link=url_for('compare_trs', html_tr_index=html_tr_index - 1, match_index=0, comparison_mode=comparison_mode, min_similarity_cutoff=min_similarity_cutoff_str),
        next_link=url_for('compare_trs', html_tr_index=html_tr_index + 1, match_index=0, comparison_mode=comparison_mode, min_similarity_cutoff=min_similarity_cutoff_str),
        prev_disabled=prev_html_tr_disabled,
        next_disabled=next_html_tr_disabled,
        current_tr_number=html_tr_index + 1,
        total_trs=total_html_trs,

        prev_match_link=url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index - 1, comparison_mode=comparison_mode, min_similarity_cutoff=min_similarity_cutoff_str),
        next_match_link=url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index + 1, comparison_mode=comparison_mode, min_similarity_cutoff=min_similarity_cutoff_str),
        go_to_best_match_link=url_for('compare_trs', html_tr_index=html_tr_index, match_index=0, comparison_mode=comparison_mode, min_similarity_cutoff=min_similarity_cutoff_str),

        prev_match_disabled=prev_match_disabled,
        next_match_disabled=next_match_disabled,
        go_to_best_match_disabled=go_to_best_match_disabled,
        current_match_number=current_match_number,
        total_matches=total_matches,

        selected_comparison_mode=comparison_mode,
        selected_min_similarity_cutoff=min_similarity_cutoff_str,

        html_tr_index=html_tr_index,
        match_index=match_index,
        apply_button_disabled_for_100_percent=apply_button_disabled_for_100_percent
    )

@app.route('/apply_template', methods=['POST'])
def apply_template():
    global initial_backup_done

    html_tr_index = request.form.get('html_tr_index', type=int)
    match_index = request.form.get('match_index', type=int)

    if html_tr_index is None or match_index is None:
        flash("Error: Missing parameters for applying template.", 'error')
        return redirect(url_for('compare_trs', html_tr_index=html_tr_index or 0, match_index=0))

    try:
        original_tr_data = comparison_results_data[html_tr_index]
        original_tr_tag_from_data = original_tr_data['html_tr_tag']

        replacement_tr_data = original_tr_data['matches'][match_index]
        replacement_tr_tag = replacement_tr_data['master_tr_tag']

        if not os.path.exists(CURRENT_HTML_PAGE_PATH):
            flash(f"Error: Current HTML file not found at '{CURRENT_HTML_PAGE_PATH}'.", 'error')
            return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index))

        with open(CURRENT_HTML_PAGE_PATH, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')

        target_original_tr_in_soup = None
        all_trs_in_reloaded_soup = soup.find_all('tr')
        original_tr_inner_html_stripped = original_tr_tag_from_data.decode_contents().strip()

        if html_tr_index < len(all_trs_in_reloaded_soup):
            potential_target_tr = all_trs_in_reloaded_soup[html_tr_index]
            if potential_target_tr.decode_contents().strip() == original_tr_inner_html_stripped:
                target_original_tr_in_soup = potential_target_tr
            else:
                print(f"DEBUG: TR at exact index {html_tr_index} does not match content. Falling back to content-based search.")
                for tr_in_soup in all_trs_in_reloaded_soup:
                    if tr_in_soup.decode_contents().strip() == original_tr_inner_html_stripped:
                        target_original_tr_in_soup = tr_in_soup
                        print(f"DEBUG: Found TR by content match.")
                        break
        else:
            print(f"DEBUG: Index {html_tr_index} is out of bounds for current TR count ({len(all_trs_in_reloaded_soup)}). Falling back to content-based search.")
            for tr_in_soup in all_trs_in_reloaded_soup:
                if tr_in_soup.decode_contents().strip() == original_tr_inner_html_stripped:
                    target_original_tr_in_soup = tr_in_soup
                    print(f"DEBUG: Found TR by content match.")
                    break

        if target_original_tr_in_soup is None:
            flash("Error: Could not locate the exact HTML TR section for replacement. The file might have changed externally, or the TR's content is ambiguous.", 'error')
            return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index))

        from copy import deepcopy
        new_tag_for_insertion = deepcopy(replacement_tr_tag)

        # Replace the original TR with the new master template TR
        target_original_tr_in_soup.replace_with(new_tag_for_insertion)

        if not initial_backup_done:
            base_name, ext = os.path.splitext(CURRENT_HTML_PAGE_PATH)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_file_path = f"{base_name}_ORIGINAL_BACKUP_{timestamp}{ext}" # More descriptive name

            shutil.copy2(CURRENT_HTML_PAGE_PATH, backup_file_path)
            flash(f"Initial backup of original HTML file created as '{os.path.basename(backup_file_path)}'.", 'info')
            initial_backup_done = True
        else:
            flash("HTML file already backed up. Overwriting current file directly.", 'info')

        with open(CURRENT_HTML_PAGE_PATH, 'w', encoding='utf-8') as f:
            prettified_content = soup.prettify()
            tabbed_content = convert_leading_spaces_to_tabs(prettified_content, spaces_per_tab=4)
            f.write(tabbed_content)

        # Reload the application data to reflect the changes in the UI
        load_application_data()

        flash("Template applied and HTML file updated successfully!", 'success')
        return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=0, comparison_mode='text', min_similarity_cutoff='50'))

    except FileNotFoundError as e:
        flash(f"Error: File not found during template application: {e}", 'error')
    except IndexError:
        flash("Error: TR index out of bounds during template application. The HTML file structure might have changed unexpectedly.", 'error')
    except Exception as e:
        flash(f"An unexpected error occurred during template application: {e}", 'error')
        import traceback
        print(f"ERROR TRACEBACK: {traceback.format_exc()}", file=sys.stderr)

    current_comparison_mode = request.args.get('comparison_mode', 'text')
    current_min_similarity_cutoff = request.args.get('min_similarity_cutoff', '50')
    return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index,
                            comparison_mode=current_comparison_mode,
                            min_similarity_cutoff=current_min_similarity_cutoff))

def convert_leading_spaces_to_tabs(html_string, spaces_per_tab=4):
    """
    Converts leading spaces in an HTML string to tab characters.
    Assumes a standard indentation of 4 spaces per tab.
    """
    lines = html_string.splitlines()
    tab_char = '\t'
    new_lines = []
    for line in lines:
        leading_spaces_match = re.match(r'^\s*', line)
        if leading_spaces_match:
            leading_spaces = leading_spaces_match.group(0)
            num_tabs = len(leading_spaces) // spaces_per_tab
            remaining_spaces = len(leading_spaces) % spaces_per_tab

            new_line = (tab_char * num_tabs) + (' ' * remaining_spaces) + line[len(leading_spaces):]
            new_lines.append(new_line)
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)

if __name__ == '__main__':
    app.run(debug=True)