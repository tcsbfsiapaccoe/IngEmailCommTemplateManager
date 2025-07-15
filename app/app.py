import os
import sys
import shutil
from datetime import datetime
import re
import uuid
import logging

from typing import List, Dict, Optional, Union
from bs4 import Tag, BeautifulSoup, NavigableString
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file # Import send_file

from Entities.Tx import Tx
from Entities.DelimiterComment import DelimiterComment
from Entities.IngMasterTemplate import IngMasterTemplate
from Entities.IngMasterTemplateGroup import IngMasterTemplateGroup

from Business.HtmlSectionComparer import HtmlSectionComparer
from Business.IngCurrentHtmlPageScanner import IngCurrentHtmlPageScanner
from Business.IngMasterTemplateScanner import IngMasterTemplateScanner

from Services.TemplateDataLoader import TemplateDataLoader
from Services.HtmlComparisonService import HtmlComparisonService
from Services.HtmlUpdaterService import HtmlUpdaterService

app = Flask(__name__)
app.secret_key = 'f3a1b5c9d7e0f2a4b6c8d0e1f3a5b7c9d1e2f4a6b8d0e4f6a8b9c1d3e5f7a9'

# --- Configure Flask Logger to ensure output to console ---
if app.logger.handlers:
    for handler in app.logger.handlers:
        app.logger.removeHandler(handler)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# --- Configuration for File Uploads ---
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'html', 'htm'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Helper function to check if a TR contains only IMG tags (and whitespace/comments) ---
def _is_image_only_tr(tr_tag: Tag) -> bool:
    """
    Checks if a given BeautifulSoup TR tag contains only TD tags, which in turn contain only IMG tags,
    whitespace, and comments. Returns True if it's image-only, False otherwise.
    """
    # First, check if the TR itself or any of its descendants (excluding comments) has significant text.
    # If there's any text that isn't just whitespace, it's not image-only.
    if tr_tag.get_text(strip=True):
        return False

    # Iterate through direct children of the TR
    for child in tr_tag.children:
        if isinstance(child, Tag):
            # A direct child of TR must be a TD. If not, it's not image-only TR.
            if child.name != 'td':
                return False
            
            # Now, check the contents of this <td> tag.
            # The <td> itself should not have significant text content *outside* of images.
            if child.get_text(strip=True): # If TD has text content (after stripping), it's not image-only
                return False
            
            # Iterate through the children of the <td> tag
            for td_child in child.children:
                if isinstance(td_child, Tag):
                    # If it's an HTML tag inside the TD, it must be an <img> tag.
                    if td_child.name != 'img':
                        return False
                    # Ensure the img tag itself doesn't contain unexpected text (shouldn't for standard img)
                    if td_child.get_text(strip=True):
                        return False
                elif isinstance(td_child, NavigableString):
                    # If it's a NavigableString (text node) inside TD, it must be only whitespace.
                    if str(td_child).strip():
                        return False
                # Other types of children (e.g., Comments) are fine and are ignored.
        elif isinstance(child, NavigableString):
            # If it's a NavigableString (text node) directly under TR, it must be only whitespace.
            if str(child).strip():
                return False
        # Other types of children (e.g., Comments) directly under TR are fine.
    return True


# --- Instantiate Services ---
master_template_scanner = IngMasterTemplateScanner()
html_page_scanner = IngCurrentHtmlPageScanner()
comparer = HtmlSectionComparer()

template_data_loader = TemplateDataLoader(master_template_scanner, html_page_scanner)
html_comparison_service = HtmlComparisonService(comparer)
html_updater_service = None

# --- Global Data Storage ---
global_template_groups: List[IngMasterTemplateGroup] = []
all_current_html_trs: List[Tag] = []
comparison_results_data: List[Dict[str, Union[Tag, List[Dict]]]] = []
initial_data_loaded = False # This flag will now primarily control master template loading and service init

def _load_application_data():
    global global_template_groups, all_current_html_trs, initial_data_loaded, html_updater_service

    master_template_path = session.get('master_template_path')
    current_html_path = session.get('current_html_path')
    original_current_filename = session.get('original_current_filename', 'modified_file.html') 

    if not master_template_path or not current_html_path:
        initial_data_loaded = False
        return

    try:
        if not os.path.exists(master_template_path):
            raise FileNotFoundError(f"Master template file not found: {master_template_path}")
        if not os.path.exists(current_html_path):
            raise FileNotFoundError(f"Current HTML file not found: {current_html_path}")

        # Load master templates only once per session or if not loaded yet
        if not initial_data_loaded:
            global_template_groups[:] = template_data_loader.load_master_template_groups(master_template_path)
            html_updater_service = HtmlUpdaterService(current_html_path)
            initial_data_loaded = True
            app.logger.info(f"Loaded {sum(len(group.ing_master_templates) for group in global_template_groups)} master templates from {os.path.basename(master_template_path)}")
        
        # ALWAYS reload current HTML TRs and full content to ensure freshness
        # This is the key change to fix the UI not updating
        all_current_html_trs[:] = html_page_scanner.get_html_page_TR_tags(current_html_path)
        
        # Removed full_current_html_content from session to prevent large cookie warning
        # with open(current_html_path, 'r', encoding='utf-8') as f:
        #     full_current_html_content = f.read()
        # session['full_current_html_content'] = full_current_html_content
        
        app.logger.info(f"Found {len(all_current_html_trs)} TRs in current HTML file: {os.path.basename(current_html_path)}")
        app.logger.info("Current HTML TRs and full content reloaded.")

    except FileNotFoundError as e:
        flash(f"Critical Error: {e}. Please re-upload files.", 'error')
        app.logger.error(f"Critical Error: {e}")
        initial_data_loaded = False
        session.pop('master_template_path', None)
        session.pop('current_html_path', None)
        session.pop('original_current_filename', None)
        session.pop('full_current_html_content', None) # Ensure it's popped if an error occurs
        session.pop('html_modified', None)
    except Exception as e:
        flash(f"Critical Error loading application data: {e}. Please re-upload files.", 'error')
        app.logger.error(f"Critical Error loading application data: {e}", exc_info=True)
        initial_data_loaded = False
        session.pop('master_template_path', None)
        session.pop('current_html_path', None)
        session.pop('original_current_filename', None)
        session.pop('full_current_html_content', None) # Ensure it's popped if an error occurs
        session.pop('html_modified', None)

@app.before_request
def before_request_load_data():
    if request.endpoint not in ['index', 'upload_files']:
        _load_application_data()

@app.route('/')
def index():
    session.pop('master_template_path', None)
    session.pop('current_html_path', None)
    session.pop('original_current_filename', None)
    session.pop('full_current_html_content', None)
    session.pop('html_modified', None)
    global initial_data_loaded
    initial_data_loaded = False
    return render_template('LandingPage.html')

@app.route('/upload_files', methods=['POST'])
def upload_files():
    if 'master_template_file' not in request.files or 'current_html_file' not in request.files:
        flash('Both Master Template and Current HTML files are required.', 'error')
        return redirect(url_for('index'))

    master_template_file = request.files['master_template_file']
    current_html_file = request.files['current_html_file']

    if master_template_file.filename == '' or current_html_file.filename == '':
        flash('No selected file for one or both inputs.', 'error')
        return redirect(url_for('index'))

    if master_template_file and allowed_file(master_template_file.filename) and \
       current_html_file and allowed_file(current_html_file.filename):
        try:
            master_filename = str(uuid.uuid4()) + "_" + master_template_file.filename
            current_filename_guid = str(uuid.uuid4()) + "_" + current_html_file.filename 

            master_path = os.path.join(UPLOAD_FOLDER, master_filename)
            current_path = os.path.join(UPLOAD_FOLDER, current_filename_guid)

            master_template_file.save(master_path)
            current_html_file.save(current_path)

            session['master_template_path'] = master_path
            session['current_html_path'] = current_path
            session['original_current_filename'] = current_html_file.filename
            session['html_modified'] = False # Initialize modification flag

            flash('Files uploaded successfully! Starting comparison.', 'success')
            return redirect(url_for('compare_trs'))

        except Exception as e:
            flash(f'Error uploading files: {e}', 'error')
            app.logger.error(f"Error during file upload: {e}", exc_info=True)
            return redirect(url_for('index'))
    else:
        flash('Invalid file type. Only HTML files are allowed (.html, .htm).', 'error')
        return redirect(url_for('index'))

@app.route('/compare_trs')
def compare_trs():
    global comparison_results_data, all_current_html_trs, html_updater_service

    _load_application_data() # Ensure data is fresh

    if not initial_data_loaded:
        flash("Please upload HTML files to start the comparison.", 'warning')
        return redirect(url_for('index'))

    html_tr_index = int(request.args.get('html_tr_index', 0))
    match_index = int(request.args.get('match_index', 0))

    # Get comparison mode from request args, or session, or default to 'text'
    current_comparison_mode = request.args.get('comparison_mode')
    if current_comparison_mode is None:
        current_comparison_mode = session.get('selected_comparison_mode', 'text')
    session['selected_comparison_mode'] = current_comparison_mode

    # Get min_similarity_cutoff from request args, or session, or default to '50'
    current_min_similarity_cutoff_str = request.args.get('min_similarity_cutoff')
    if current_min_similarity_cutoff_str is None:
        current_min_similarity_cutoff_str = session.get('selected_min_similarity_cutoff', '50') # Default to '50'
    session['selected_min_similarity_cutoff'] = current_min_similarity_cutoff_str
    current_min_similarity_cutoff = int(current_min_similarity_cutoff_str)

    # Get selected_template_group from request args, or session, or default to ''
    current_selected_template_group = request.args.get('selected_template_group')
    if current_selected_template_group is None:
        current_selected_template_group = session.get('selected_template_group', '')
    session['selected_template_group'] = current_selected_template_group


    comparison_results_data = html_comparison_service.perform_comparison(
        all_current_html_trs,
        global_template_groups,
        current_comparison_mode,
        current_min_similarity_cutoff,
        current_selected_template_group
    )

    total_trs = len(all_current_html_trs)
    current_tr_html = "<p>No content to display.</p>"
    master_tr_html = "<p>No matches.</p>"
    total_matches = 0
    text_percentage = 'N/A'
    hierarchy_percentage = 'N/A'
    combined_percentage = 'N/A'
    apply_button_disabled_for_100_percent = 'disabled'

    # Do NOT retrieve full_current_html from session here. It's no longer stored there.
    # We will read it directly in the download route.
    full_current_html = "" # Initialize as empty, as it's not needed for rendering here
    original_current_filename = session.get('original_current_filename', 'modified_file.html')
    html_modified = session.get('html_modified', False) # Retrieve the modification flag

    if total_trs > 0:
        html_tr_index = max(0, min(html_tr_index, total_trs - 1))
        
        current_tr_object = all_current_html_trs[html_tr_index]
        current_tr_html = f"<table><tbody><tr>{str(current_tr_object)}</tr></tbody></table>"

        matches_for_current_tr = comparison_results_data[html_tr_index]['matches']
        total_matches = len(matches_for_current_tr)

        if matches_for_current_tr:
            match_index = max(0, min(match_index, total_matches - 1))
            current_match = matches_for_current_tr[match_index]
            master_tr_html = f"<table><tbody><tr>{str(current_match['master_template'].template_element)}</tr></tbody></table>"
            
            text_percentage = f"{current_match['inner_text_score']:.2f}%"
            hierarchy_percentage = f"{current_match['structure_score']:.2f}%"
            combined_percentage = f"{current_match['combined_score']:.2f}%"

            # Determine if current_tr and master_template are image-only
            is_current_tr_image_only = _is_image_only_tr(current_tr_object)
            is_master_template_image_only = _is_image_only_tr(current_match['master_template'].template_element)

            # Logic for enabling/disabling the "Apply" button
            if current_match['combined_score'] < 100.0: # If not a perfect match
                apply_button_disabled_for_100_percent = ''
            elif current_match['combined_score'] == 100.0 and is_current_tr_image_only and is_master_template_image_only:
                # If perfect match AND both are image-only, button should be enabled
                apply_button_disabled_for_100_percent = ''
            else: 
                # If perfect match AND at least one is NOT image-only (meaning it has text), button should be disabled
                apply_button_disabled_for_100_percent = 'disabled'
        else:
            flash("No matches found for this TR with current criteria.", 'info')
            apply_button_disabled_for_100_percent = 'disabled' # Ensure disabled if no matches

    prev_link = url_for('compare_trs', html_tr_index=html_tr_index - 1, match_index=0, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    next_link = url_for('compare_trs', html_tr_index=html_tr_index + 1, match_index=0, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    prev_disabled = 'disabled' if html_tr_index == 0 else ''
    next_disabled = 'disabled' if html_tr_index >= total_trs - 1 else ''

    prev_match_link = url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index - 1, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    next_match_link = url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index + 1, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    prev_match_disabled = 'disabled' if total_matches == 0 or match_index == 0 else ''
    next_match_disabled = 'disabled' if total_matches == 0 or match_index >= total_matches - 1 else ''

    go_to_best_match_link = url_for('compare_trs', html_tr_index=html_tr_index, match_index=0, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    go_to_best_match_disabled = 'disabled' if total_matches == 0 or match_index == 0 else ''

    template_group_names = sorted([group.template_group_name for group in global_template_groups])

    return render_template(
        'index.html',
        html_tr_index=html_tr_index,
        match_index=match_index,
        current_tr_html=current_tr_html,
        master_tr_html=master_tr_html,
        text_percentage=text_percentage,
        hierarchy_percentage=hierarchy_percentage,
        combined_percentage=combined_percentage,
        total_trs=total_trs,
        current_tr_number=html_tr_index + 1,
        total_matches=total_matches,
        current_match_number=match_index + 1 if total_matches > 0 else 0,
        
        prev_link=prev_link,
        next_link=next_link,
        prev_disabled=prev_disabled,
        next_disabled=next_disabled,
        prev_match_link=prev_match_link,
        next_match_link=next_match_link,
        prev_match_disabled=prev_match_disabled,
        next_match_disabled=next_match_disabled,
        go_to_best_match_link=go_to_best_match_link,
        go_to_best_match_disabled=go_to_best_match_disabled,
        apply_button_disabled_for_100_percent=apply_button_disabled_for_100_percent,

        selected_comparison_mode=current_comparison_mode,
        selected_min_similarity_cutoff=current_min_similarity_cutoff_str,
        selected_template_group=current_selected_template_group,
        template_group_names=template_group_names,
        
        # full_current_html is no longer passed from here. It will be read on demand.
        # original_current_filename is still needed for the download filename.
        original_current_filename=original_current_filename,
        html_modified=html_modified, # Pass the flag to the template

        comparison_results=comparison_results_data # Pass the full comparison results
    )

@app.route('/apply_template', methods=['POST'])
def apply_template():
    global all_current_html_trs, html_updater_service

    _load_application_data() # Ensure data is fresh
    if not initial_data_loaded or html_updater_service is None:
        flash("Application data not loaded or updater service not initialized. Please re-upload files.", 'error')
        return redirect(url_for('index'))

    html_tr_index = int(request.form.get('html_tr_index', 0))
    match_index = int(request.form.get('match_index', 0))
    
    current_comparison_mode = request.form.get('comparison_mode', session.get('selected_comparison_mode', 'text'))
    current_min_similarity_cutoff_str = request.form.get('min_similarity_cutoff', session.get('selected_min_similarity_cutoff', '50'))
    current_selected_template_group = request.form.get('selected_template_group', session.get('selected_template_group', ''))

    if not all_current_html_trs or not comparison_results_data:
        flash("Error: No current HTML TRs or comparison results loaded.", 'error')
        return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index,
                                 comparison_mode=current_comparison_mode,
                                 min_similarity_cutoff=current_min_similarity_cutoff_str,
                                 selected_template_group=current_selected_template_group))

    try:
        original_tr_element = all_current_html_trs[html_tr_index]
        
        matches_for_current_tr = comparison_results_data[html_tr_index]['matches']
        
        if not matches_for_current_tr:
            flash("No valid match found to apply.", 'error')
            return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index,
                                     comparison_mode=current_comparison_mode,
                                     min_similarity_cutoff=current_min_similarity_cutoff_str,
                                     selected_template_group=current_selected_template_group))

        replacement_master_template = matches_for_current_tr[match_index]['master_template']
        replacement_tr_element = replacement_master_template.template_element

        html_updater_service.apply_template_to_html(
            original_tr_element,
            replacement_tr_element
        )

        # Re-load application data immediately after modification to refresh in-memory state
        _load_application_data() 
        session['html_modified'] = True # Set flag to indicate modification has occurred

        flash(f"Template '{replacement_master_template.template_name}' from group '{replacement_master_template.delimiter.start.split(' ')[1]}' applied and HTML file updated successfully!", 'success')
        return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=0,
                                 comparison_mode=current_comparison_mode,
                                 min_similarity_cutoff=current_min_similarity_cutoff_str,
                                 selected_template_group=current_selected_template_group))

    except (FileNotFoundError, ValueError, IndexError) as e:
        flash(f"Error applying template: {e}", 'error')
    except Exception as e:
        flash(f"An unexpected error occurred during template application: {e}", 'error')
        import traceback
        app.logger.error(f"ERROR TRACEBACK: {traceback.format_exc()}", exc_info=True)
        
    return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index,
                             comparison_mode=current_comparison_mode,
                             min_similarity_cutoff=current_min_similarity_cutoff_str,
                             selected_template_group=current_selected_template_group))

@app.route('/download_modified_html')
def download_modified_html():
    current_html_path = session.get('current_html_path')
    original_filename = session.get('original_current_filename', 'modified_file.html')

    if not current_html_path or not os.path.exists(current_html_path):
        flash("Error: Modified HTML file not found for download.", 'error')
        return redirect(url_for('compare_trs')) # Redirect to the comparison page

    try:
        # Read the file content directly from disk for download
        return send_file(current_html_path, as_attachment=True, download_name=original_filename, mimetype='text/html')
    except Exception as e:
        flash(f"Error preparing file for download: {e}", 'error')
        app.logger.error(f"Error during file download: {e}", exc_info=True)
        return redirect(url_for('compare_trs'))

if __name__ == '__main__':
    app.run(debug=True)