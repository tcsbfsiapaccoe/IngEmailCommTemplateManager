README for TR Comparison Viewer

This guide will help you set up and run the HTML TR Comparison Viewer application.

1)  **Ensure that you have Visual Studio Code IDE installed.**
    You can install it from: [https://code.visualstudio.com/download](https://code.visualstudio.com/download)

2)  **Ensure that you have the latest version of Python installed.**
    You can install it from: [https://www.python.org/downloads/](https://www.python.org/downloads/)
    (It is recommended to install Python 3.8 or newer.)

3)  **Keep your Master Template HTML file and all your Current HTML files in the `.\uploads\` folder.**
    This folder will be automatically created in the same directory as your `app.py` file if it doesn't exist.

4)  **Open VS Code, and open the location where your `app.py` file is present.**
    (File > Open Folder... then select the folder containing `app.py`).

5)  **Open a terminal** (Terminal > New Terminal in VS Code), and **invoke the "virtual environment" (`.venv`)** by running one of these commands, depending on your operating system:

    * **On Windows (Command Prompt/PowerShell):**
        ```bash
        .venv\Scripts\activate
        ```
    * **On macOS/Linux (Bash/Zsh):**
        ```bash
        source .venv/bin/activate
        ```
    * **If you haven't created a virtual environment yet, first run:**
        ```bash
        python -m venv .venv
        ```
        Then run the appropriate activation command above.

6)  **Install the required Python packages.** While the virtual environment is active, run:
    ```bash
    pip install Flask beautifulsoup4 fuzzywuzzy python-Levenshtein
    ```
    *Note: `python-Levenshtein` is an optional dependency for `fuzzywuzzy` that provides faster string comparison. If you encounter issues installing it, you can omit it, and `fuzzywuzzy` will fall back to a pure Python implementation.*

7)  **Run this command on the Terminal.**
    ```bash
    python app.py
    ```

8)  You will see output on the Terminal screen, including a line that looks like `* Running on http://127.0.0.1:5000` (or similar, typically port 5000). **Open this link in your web browser** to access the application.

This invokes the application, and you can then use the web interface to upload your HTML files and perform comparisons.
