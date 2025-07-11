import os
import shutil
from datetime import datetime
from bs4 import BeautifulSoup, Tag

class HtmlUpdaterService:
    """
    Service class responsible for updating the current HTML file by replacing
    a specific TR element with a new one. It also handles creating backups.
    """
    def __init__(self, current_html_file_path: str):
        if not os.path.exists(current_html_file_path):
            raise FileNotFoundError(f"Current HTML file not found at initialization: {current_html_file_path}")
        self._current_html_file_path = current_html_file_path
        self._initial_backup_done = False

    def _create_backup(self):
        """
        Creates a timestamped backup of the current HTML file if it hasn't been backed up yet.
        """
        if not self._initial_backup_done:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = os.path.join(os.path.dirname(self._current_html_file_path), "backups")
                os.makedirs(backup_dir, exist_ok=True)
                
                base_name = os.path.basename(self._current_html_file_path)
                name, ext = os.path.splitext(base_name)
                backup_filename = f"{name}_backup_{timestamp}{ext}"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                shutil.copy2(self._current_html_file_path, backup_path)
                print(f"Backup created at: {backup_path}")
                self._initial_backup_done = True
            except Exception as e:
                print(f"Error creating backup: {e}", file=sys.stderr)

    def apply_template_to_html(self, original_tr: Tag, replacement_tr: Tag):
        """
        Replaces a specific <tr> element in the current HTML file with a new <tr> element.
        Creates a backup of the original file before making changes.

        Args:
            original_tr (Tag): The BeautifulSoup Tag object of the <tr> to be replaced.
            replacement_tr (Tag): The BeautifulSoup Tag object of the <tr> to insert.

        Raises:
            ValueError: If the original_tr is not found in the document.
            FileNotFoundError: If the current HTML file cannot be found or accessed.
            Exception: For other file write errors.
        """
        self._create_backup() # Ensure backup is made before any modification

        if not os.path.exists(self._current_html_file_path):
            raise FileNotFoundError(f"Current HTML file not found: {self._current_html_file_path}")

        try:
            with open(self._current_html_file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')

            # Find the original TR in the parsed soup.
            # We need to find it by its content/structure, as the original_tr object
            # passed in might be from a previous parse and not directly attached to this soup.
            # A robust way is to convert original_tr to string and find it,
            # or if it has a unique ID/class, use that.
            # For simplicity, we'll try to find an exact match of its string representation.
            # This can be made more robust if TRs have unique identifiers.

            # Simple approach: Find all <tr> tags and compare their string representation
            # This assumes the original_tr's string content is unique enough to find it.
            found_original = None
            all_trs_in_soup = soup.find_all('tr', recursive=False) # Only direct <tr> children of tables

            # Find the actual element in the current soup that matches the original_tr
            # This is a critical step. If original_tr has an ID, use soup.find(id=original_tr.id)
            # Otherwise, we need a way to reliably locate it.
            # For now, let's assume `original_tr` has a parent and can be replaced in the soup.
            # A more robust solution would involve passing an index or a unique identifier.

            # A safer way to find the element is to re-parse the current_html_file_path
            # and then find the element by its index, or by comparing its content.
            # Given that all_current_html_trs is a global list indexed, we can rely on that index.
            # However, `original_tr` here is a detached Tag object.
            
            # Let's use a robust way to find the original_tr in the current soup:
            # Iterate through all TRs in the *current* soup and compare their HTML content
            # with the HTML content of the `original_tr` object passed in.
            
            # Convert original_tr to a canonical string for comparison
            original_tr_html_str = str(original_tr)

            target_element_in_soup = None
            for tr_in_soup in soup.find_all('tr', recursive=True): # Search all trs
                if str(tr_in_soup) == original_tr_html_str:
                    target_element_in_soup = tr_in_soup
                    break

            if target_element_in_soup:
                target_element_in_soup.replace_with(replacement_tr)
            else:
                raise ValueError(f"Original TR element not found in the HTML document.")

            with open(self._current_html_file_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            print(f"Successfully replaced TR in {self._current_html_file_path}")

        except FileNotFoundError:
            raise # Re-raise if file not found after backup attempt
        except Exception as e:
            raise Exception(f"Failed to apply template to HTML file: {e}")