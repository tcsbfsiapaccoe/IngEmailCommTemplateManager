import os
import sys
import shutil
from datetime import datetime
import re
import uuid

from typing import List, Dict, Optional, Union
from bs4 import Tag, BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for, flash, session

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
# A strong, unique secret key is required for the flask to flash messages and manage sessions.
app.secret_key = 'f3a1b5c9d7e0f2a4b6c8d0e1f3a5b7c9d1e2f4a6b8d0e4f6a8b9c1d3e5f7a9'

# Prepare to store uploaded files
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'html', 'htm'}

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Business logic components
master_template_scanner = IngMasterTemplateScanner()
html_page_scanner = IngCurrentHtmlPageScanner()
comparer = HtmlSectionComparer()

# Service layer components
template_data_loader = TemplateDataLoader(master_template_scanner, html_page_scanner)
html_comparison_service = HtmlComparisonService(comparer)
html_updater_service = None

global_template_groups: List[IngMasterTemplateGroup] = []
all_current_html_trs: List[Tag] = []
comparison_results_data: List[Dict[str, Union[Tag, List[Dict]]]] = []
initial_data_loaded = False

def _load_application_data():
    global global_template_groups, all_current_html_trs, initial_data_loaded, html_updater_service

    # Retrieve file paths from session
    master_template_path = session.get('master_template_path')
    current_html_path = session.get('current_html_path')

    if not master_template_path or not current_html_path:
        # If index.html page is accessed before files are uploaded,
        # or if session paths are not set, we do not load any data.
        initial_data_loaded = False
        return

    if not initial_data_loaded:
        try:
            # Check if files actually exist on disk
            if not os.path.exists(master_template_path):
                raise FileNotFoundError(f"Master template file not found: {master_template_path}")
            if not os.path.exists(current_html_path):
                raise FileNotFoundError(f"Current HTML file not found: {current_html_path}")

            global_template_groups = template_data_loader.load_master_template_groups(master_template_path)
            all_current_html_trs = template_data_loader.load_current_html_trs(current_html_path)
            
            html_updater_service = HtmlUpdaterService(current_html_path)
            initial_data_loaded = True

            print("Application data (Master Templates and Current HTML TRs) loaded successfully from session files.")
        except FileNotFoundError as e:
            flash(f"Critical Error: {e}. Please re-upload files.", 'error')
            print(f"Critical Error: {e}", file=sys.stderr)
            initial_data_loaded = False # Reset flag on error
        except Exception as e:
            flash(f"Critical Error loading application data: {e}. Please re-upload files.", 'error')
            print(f"Critical Error loading application data: {e}", file=sys.stderr)
            import traceback
            print(f"ERROR TRACEBACK: {traceback.format_exc()}", file=sys.stderr)
            initial_data_loaded = False # Reset flag on error

@app.before_request
def before_request_load_data():
    """Ensures application data is loaded if file paths are in session."""
    # Only try to load data if we are not on the upload page itself
    if request.endpoint not in ['index', 'upload_files']:
        _load_application_data()

@app.route('/')
def index():
    session.pop('master_template_path', None)
    session.pop('current_html_path', None)
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
            # Generate unique filenames to avoid conflicts
            master_filename = str(uuid.uuid4()) + os.path.splitext(master_template_file.filename)[1]
            current_filename = str(uuid.uuid4()) + os.path.splitext(current_html_file.filename)[1]

            master_path = os.path.join(UPLOAD_FOLDER, master_filename)
            current_path = os.path.join(UPLOAD_FOLDER, current_filename)

            master_template_file.save(master_path)
            current_html_file.save(current_path)

            # Store file paths in session
            session['master_template_path'] = master_path
            session['current_html_path'] = current_path

            flash('Files uploaded successfully! Starting comparison.', 'success')
            return redirect(url_for('compare_trs'))

        except Exception as e:
            flash(f'Error uploading files: {e}', 'error')
            print(f"Error during file upload: {e}", file=sys.stderr)
            import traceback
            print(f"ERROR TRACEBACK: {traceback.format_exc()}", file=sys.stderr)
            return redirect(url_for('index'))
    else:
        flash('Invalid file type. Only HTML files are allowed (.html, .htm).', 'error')
        return redirect(url_for('index'))

@app.route('/compare_trs')
def compare_trs():
    global comparison_results_data, all_current_html_trs, html_updater_service

    # Ensure data is loaded from session files
    _load_application_data()

    if not initial_data_loaded:
        flash("Please upload HTML files to start the comparison.", 'warning')
        return redirect(url_for('index'))

    # Get current TR index and match index from request arguments, default to 0
    html_tr_index = int(request.args.get('html_tr_index', 0))
    match_index = int(request.args.get('match_index', 0))

    # Get comparison parameters from request arguments
    current_comparison_mode = request.args.get('comparison_mode', 'text') # Default to 'text'
    current_min_similarity_cutoff_str = request.args.get('min_similarity_cutoff', '50') # Default to '50'
    current_min_similarity_cutoff = int(current_min_similarity_cutoff_str)
    current_selected_template_group = request.args.get('selected_template_group', '')

    # Perform comparison
    comparison_results_data = html_comparison_service.perform_comparison(
        all_current_html_trs,
        global_template_groups,
        current_comparison_mode,
        current_min_similarity_cutoff,
        current_selected_template_group
    )

    # Prepare data for rendering
    total_trs = len(all_current_html_trs)
    current_tr_html = "<p>No content to display.</p>"
    master_tr_html = "<p>No matches.</p>"
    current_match = None
    total_matches = 0
    text_percentage = 'N/A'
    hierarchy_percentage = 'N/A'
    combined_percentage = 'N/A'
    apply_button_disabled_for_100_percent = 'disabled'

    if total_trs > 0:
        # Ensure indices are within bounds
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

            # Enable apply button only if there's a match and it's not 100% identical
            if current_match['inner_text_score'] != 100 or current_match['structure_score'] != 100:
                apply_button_disabled_for_100_percent = ''
        else:
            flash("No matches found for this TR with current criteria.", 'info')

    # Prepare navigation links and disabled states
    prev_link = url_for('compare_trs', html_tr_index=html_tr_index - 1, match_index=0, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    next_link = url_for('compare_trs', html_tr_index=html_tr_index + 1, match_index=0, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    prev_disabled = 'disabled' if html_tr_index == 0 else ''
    next_disabled = 'disabled' if html_tr_index >= total_trs - 1 else ''

    prev_match_link = url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index - 1, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    next_match_link = url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index + 1, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    prev_match_disabled = 'disabled' if match_index == 0 else ''
    next_match_disabled = 'disabled' if match_index >= total_matches - 1 else ''

    go_to_best_match_link = url_for('compare_trs', html_tr_index=html_tr_index, match_index=0, comparison_mode=current_comparison_mode, min_similarity_cutoff=current_min_similarity_cutoff_str, selected_template_group=current_selected_template_group)
    go_to_best_match_disabled = 'disabled' if total_matches == 0 or match_index == 0 else ''

    # Extract template group names for the dropdown
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
        
        # Navigation controls
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

        # Options values for rendering form
        selected_comparison_mode=current_comparison_mode,
        selected_min_similarity_cutoff=current_min_similarity_cutoff_str,
        selected_template_group=current_selected_template_group,
        template_group_names=template_group_names
    )

@app.route('/apply_template', methods=['POST'])
def apply_template():
    global all_current_html_trs, html_updater_service

    # Ensure data is loaded and html_updater_service is initialized
    _load_application_data()
    if not initial_data_loaded or html_updater_service is None:
        flash("Application data not loaded or updater service not initialized. Please re-upload files.", 'error')
        return redirect(url_for('index'))

    html_tr_index = int(request.form.get('html_tr_index', 0))
    match_index = int(request.form.get('match_index', 0))
    
    # Retrieve current filter options from the form to re-apply them after redirect
    current_comparison_mode = request.form.get('comparison_mode', 'text')
    current_min_similarity_cutoff_str = request.form.get('min_similarity_cutoff', '50')
    current_selected_template_group = request.form.get('selected_template_group', '')

    if not all_current_html_trs or not comparison_results_data:
        flash("Error: No current HTML TRs or comparison results loaded.", 'error')
        return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index,
                                 comparison_mode=current_comparison_mode,
                                 min_similarity_cutoff=current_min_similarity_cutoff_str,
                                 selected_template_group=current_selected_template_group))

    try:
        # Get the original TR element to be replaced from the global list
        original_tr_element = all_current_html_trs[html_tr_index]
        
        # Get the replacement TR element from the comparison results
        matches_for_current_tr = comparison_results_data[html_tr_index]['matches']
        
        if not matches_for_current_tr:
            flash("No valid match found to apply.", 'error')
            return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index,
                                     comparison_mode=current_comparison_mode,
                                     min_similarity_cutoff=current_min_similarity_cutoff_str,
                                     selected_template_group=current_selected_template_group))

        replacement_master_template = matches_for_current_tr[match_index]['master_template']
        replacement_tr_element = replacement_master_template.template_element

        # Use the service to apply the template
        html_updater_service.apply_template_to_html(
            original_tr_element,
            replacement_tr_element
        )

        # After applying, re-load the current HTML TRs to reflect the change
        # This is crucial because the Tag objects in `all_current_html_trs`
        # are detached from the updated file content.
        _load_application_data()

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
        print(f"ERROR TRACEBACK: {traceback.format_exc()}", file=sys.stderr)

    # If any error occurs, redirect back to the current view
    return redirect(url_for('compare_trs', html_tr_index=html_tr_index, match_index=match_index,
                             comparison_mode=current_comparison_mode,
                             min_similarity_cutoff=current_min_similarity_cutoff_str,
                             selected_template_group=current_selected_template_group))

# Check allowed file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    app.run(debug=True)