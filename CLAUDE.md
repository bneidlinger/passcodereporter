# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bosch Security Systems Report Generator - A Python application that parses Bosch B9512G panel user export files and generates interactive HTML reports with access control data.

## Core Architecture

Single-file Python application (`userreporter.py`) with three main components:

1. **Parser**: `parse_bosch_txt()` - Handles Bosch's peculiar text format with:
   - Comma-separated values with inconsistent spacing
   - User data deduplication by User ID
   - Automatic filtering of placeholder users (User* with no passcode)
   - Space removal from broken word formatting in usernames

2. **Report Generator**: `generate_html()` - Creates self-contained HTML with:
   - JavaScript password protection
   - Inline editing with visual modification tracking
   - Pagination (50 users per page)
   - Delete/restore functionality with strikethrough visualization
   - Export capability for modified reports

3. **GUI**: `run_gui()` - Tkinter interface styled as retro DOS terminal

## Development Commands

```bash
# Run the application
python userreporter.py

# No external dependencies required - uses only Python standard library
```

## Data Format

Input: Bosch TXT export files with format:
- Header lines with account info
- User data lines: `User [ID],User Nam e ,Pass code ,[groups/access],A1-A8 Auth levels`
- Multiple pages separated by timestamp lines
- Inconsistent spacing that needs cleanup

## Key Implementation Details

- **Deduplication**: Tracks users by ID to handle multi-page exports
- **Auth Levels**: Scans A1-A8 columns, assigns first non-zero value
- **Logo Embedding**: Embeds images as base64 (warns if >100KB)
- **Report State**: Tracks added/modified/deleted rows with CSS classes
- **Security**: Password field uses type="password" masking in GUI