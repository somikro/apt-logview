#!/usr/bin/env python3
import sys
import re
import argparse

def clean_apt_log(input_stream, output_stream, keep_color=False):
    # Regex to match common apt terminal progress markers and percentage loops
    progress_pattern = re.compile(r'Progress:\s*\[|\]\s*\d+%\s*|Fetching:|Extracting:')
    
    # Regex to match ANSI escape sequences (colors, bold formatting, cursor controls)
    ansi_escape_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    for line in input_stream:
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
        help="Path to the raw input log file. If omitted, reads from stdin."
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
    
    args = parser.parse_args()

    # 1. Resolve Input Stream (File vs Stdin)
    if args.input:
        try:
            infile = open(args.input, 'r', encoding='utf-8', errors='ignore')
        except FileNotFoundError:
            sys.stderr.write(f"Error: The file '{args.input}' does not exist.\n")
            sys.exit(1)
        except PermissionError:
            sys.stderr.write(f"Error: Permission denied reading '{args.input}'.\n")
            sys.exit(1)
    else:
        infile = sys.stdin

    # 2. Resolve Output Stream (File vs Stdout) & Execute
    try:
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as outfile:
                    clean_apt_log(infile, outfile, keep_color=args.color)
            except PermissionError:
                sys.stderr.write(f"Error: Permission denied writing to '{args.output}'.\n")
                sys.exit(1)
        else:
            clean_apt_log(infile, sys.stdout, keep_color=args.color)
    finally:
        # Safely close the input file if we opened one
        if args.input:
            infile.close()
            
    # 3. Ensure a clean terminal hand-off back to Bash
    sys.stdout.flush()
    sys.stderr.flush()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\nProcess interrupted by user.\n")
        sys.exit(130)
