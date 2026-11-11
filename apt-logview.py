#!/usr/bin/env python3
"""Parse and display APT log sessions, allowing users to view and clean specific sessions."""   
__version__ = "1.1.0"
import sys
import re
import argparse
from datetime import datetime

def parse_apt_sessions(log_file_path):
    """Parse the apt log file and extract session information."""
    sessions = []
    current_session = None
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Check for session start
                if line.startswith('Log started:'):
                    if current_session:
                        sessions.append(current_session)
                    timestamp = line.replace('Log started:', '').strip()
                    current_session = {
                        'start_timestamp': timestamp,
                        'end_timestamp': None,
                        'line_count': 0,
                        'packages': []
                    }
                # Check for session end
                elif line.startswith('Log ended:'):
                    if current_session:
                        timestamp = line.replace('Log ended:', '').strip()
                        current_session['end_timestamp'] = timestamp
                        sessions.append(current_session)
                        current_session = None
                # Extract package information if we're in a session
                elif current_session:
                    current_session['line_count'] += 1
                    # Look for package operations
                    if 'Selecting' in line or 'Unpacking' in line or 'Setting up' in line:
                        package_match = re.search(
                            r'(Selecting|Unpacking|Setting up)\s+([^\s]+)', line
                        )
                        if package_match:
                            current_session['packages'].append(package_match.group(2))
    except Exception as e:
        sys.stderr.write(f"Error reading log file: {e}\n")
        sys.exit(1)
    
    # Add any incomplete session (shouldn't happen with well-formed logs)
    if current_session:
        sessions.append(current_session)
    
    return sessions

def display_session_menu(sessions):
    """Display available sessions and prompt user to select one."""
    if not sessions:
        sys.stderr.write("No apt sessions found in the log file.\n")
        sys.exit(1)
    
    print("\nAvailable APT sessions:")
    print("-" * 80)
    
    for idx, session in enumerate(sessions, 1):
        start = session['start_timestamp']
        end = session['end_timestamp'] if session['end_timestamp'] else 'N/A'
        pkg_count = len(session['packages'])
        print(f"{idx}. Started: {start}")
        print(f"   Ended:   {end}")
        print(f"   Packages affected: {pkg_count}")
        if pkg_count > 0 and pkg_count <= 5:
            print(f"   Packages: {', '.join(session['packages'][:5])}")
        elif pkg_count > 5:
            print(f"   Packages: {', '.join(session['packages'][:5])} ... and {pkg_count - 5} more")
        print()
    
    while True:
        try:
            choice = input("Select session number (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                sys.exit(0)
            session_num = int(choice)
            if 1 <= session_num <= len(sessions):
                return session_num - 1
            else:
                print(f"Please enter a number between 1 and {len(sessions)}.")
        except ValueError:
            print("Invalid input. Please enter a valid session number.")

def extract_session_from_log(log_file_path, session_index):
    """Extract a specific session from the log file."""
    sessions_found = 0
    in_selected_session = False
    session_lines = []
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('Log started:'):
                    if sessions_found == session_index:
                        in_selected_session = True
                    sessions_found += 1
                
                if in_selected_session:
                    session_lines.append(line)
                    if line.startswith('Log ended:'):
                        break
    except Exception as e:
        sys.stderr.write(f"Error reading log file: {e}\n")
        sys.exit(1)
    
    return session_lines

def clean_apt_log(input_lines, output_stream, keep_color=False):
    """Clean and format apt log lines."""
    # Regex to match common apt terminal progress markers and percentage loops
    progress_pattern = re.compile(r'Progress:\s*\[|\]\s*\d+%\s*|Fetching:|Extracting:')
    
    # Regex to match ANSI escape sequences (colors, bold formatting, cursor controls)
    ansi_escape_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    for line in input_lines:
        # Drop any lines belonging to the "Reading database" block completely
        if "(Reading database" in line or "files and directories currently installed" in line:
            continue
            
        # Process lines to handle carriage returns (\r)
        sub_lines = line.split('\r')
        cleaned_sub_lines = []
        
        for sub in sub_lines:
            if progress_pattern.search(sub):
                continue
            cleaned_sub_lines.append(sub)
        
        if cleaned_sub_lines:
            final_line = "".join(cleaned_sub_lines).rstrip('\r\n')
            if final_line.strip():
                # Strip colors if requested
                if not keep_color:
                    final_line = ansi_escape_pattern.sub('', final_line)
                
                # Write the line and cleanly re-terminate it
                output_stream.write(final_line + '\n')
    
    # Force flush the output buffer
    output_stream.flush()

def main():
    parser = argparse.ArgumentParser(
        description="Sanitize Debian APT terminal logs by removing progress spam and database reading sequences."
    )
    parser.add_argument(
        "-i", "--input", 
        help="Path to the raw input log file. If omitted, uses /var/log/apt/term.log."
    )
    parser.add_argument(
        "-o", "--output", 
        help="Path to the output file. If omitted, outputs directly to stdout."
    )
    parser.add_argument(
        "-c", "--color", 
        action="store_true", 
        help="Keep ANSI escape/color codes intact for reading via 'less -R'."
    )
    parser.add_argument(
        "-s", "--session", 
        type=int,
        help="Select session by number (1-based). If omitted, shows interactive menu."
    )
    
    args = parser.parse_args()
    
    # Determine input file
    input_file = args.input if args.input else '/var/log/apt/term.log'
    
    # 1. Parse sessions from the log file
    sessions = parse_apt_sessions(input_file)
    
    # 2. Determine which session to process
    if args.session:
        if args.session < 1 or args.session > len(sessions):
            sys.stderr.write(f"Error: Session {args.session} does not exist. Found {len(sessions)} sessions.\n")
            sys.exit(1)
        selected_index = args.session - 1
    else:
        selected_index = display_session_menu(sessions)
    
    # 3. Extract the selected session
    session_lines = extract_session_from_log(input_file, selected_index)
    
    # 4. Process and output
    try:
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as outfile:
                    clean_apt_log(session_lines, outfile, keep_color=args.color)
                    print(f"\nSession {selected_index + 1} written to: {args.output}", file=sys.stderr)
            except PermissionError:
                sys.stderr.write(f"Error: Permission denied writing to '{args.output}'.\n")
                sys.exit(1)
        else:
            clean_apt_log(session_lines, sys.stdout, keep_color=args.color)
    finally:
        # 5. Ensure a clean terminal hand-off back to Bash
        sys.stdout.flush()
        sys.stderr.flush()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\nProcess interrupted by user.\n")
        sys.exit(130)
