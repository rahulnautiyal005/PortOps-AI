import PyPDF2
import pdfplumber
import re
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import sys
import os

class PDFEventExtractor:
    def __init__(self):
        # Common event patterns found in maritime/shipping documents
        self.event_patterns = [
            r'notice of readiness',
            r'dropped anchor',
            r'pilot on board',
            r'free pratique granted',
            r'commence.*survey',
            r'cargo operation',
            r'vessel sailed',
            r'arrived pilot station',
            r'nor tendered',
            r'first line ashore',
            r'all fast',
            r'cargo documentation',
            r'eta next port',
            r'completed.*survey',
            r'commenced.*operation'
        ]
        
        # Date patterns
        self.date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2019-10-11
            r'\d{2}-\d{2}-\d{4}',  # 11-10-2019
            r'\d{1,2}th\s+\w+\s+\d{4}',  # 11th October 2019
            r'\w+\s+\d{1,2},?\s+\d{4}',  # October 11, 2019
        ]
        
        # Time patterns
        self.time_patterns = [
            r'\d{2}:\d{2}',  # 05:00
            r'\d{1,2}\.\d{2}',  # 5.00
            r'\d{2}\s*HRS',  # 05 HRS
        ]

    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using multiple methods for better accuracy"""
        text_content = []
        
        try:
            # Method 1: Use pdfplumber (better for complex layouts)
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    if page_num >= 30:  # Limit to 30 pages
                        break
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
        except:
            # Method 2: Fallback to PyPDF2
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page_num in range(min(len(reader.pages), 30)):
                        page = reader.pages[page_num]
                        text = page.extract_text()
                        if text:
                            text_content.append(text)
            except Exception as e:
                print(f"Error extracting text: {e}")
                return ""
        
        return "\n".join(text_content)

    def normalize_date(self, date_str):
        """Normalize different date formats to YYYY-MM-DD"""
        date_str = date_str.strip()
        
        # Try different date formats
        formats = [
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%m-%d-%Y',
            '%d %B %Y',
            '%B %d, %Y',
            '%d %b %Y',
            '%b %d, %Y'
        ]
        
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime('%Y-%m-%d')
            except:
                continue
        
        # Handle special cases like "11th October 2019"
        date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime('%Y-%m-%d')
            except:
                continue
        
        return date_str  # Return original if can't parse

    def normalize_time(self, time_str):
        """Normalize different time formats to HH:MM"""
        time_str = time_str.strip().upper()
        
        # Remove common suffixes
        time_str = re.sub(r'\s*(HRS|HOURS?)\s*$', '', time_str)
        
        # Convert decimal format to HH:MM
        if '.' in time_str:
            try:
                hours, minutes = time_str.split('.')
                hours = int(hours)
                minutes = int(float('0.' + minutes) * 60)
                return f"{hours:02d}:{minutes:02d}"
            except:
                pass
        
        # Handle HH:MM format
        if ':' in time_str:
            try:
                parts = time_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                return f"{hours:02d}:{minutes:02d}"
            except:
                pass
        
        return time_str

    def extract_events(self, text):
        """Extract events with dates and times from text"""
        events = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for event patterns
            for pattern in self.event_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    event_name = self.clean_event_name(line, pattern)
                    
                    # Extract date
                    date_match = None
                    for date_pattern in self.date_patterns:
                        match = re.search(date_pattern, line)
                        if match:
                            date_match = match.group()
                            break
                    
                    # Extract time
                    time_match = None
                    for time_pattern in self.time_patterns:
                        match = re.search(time_pattern, line)
                        if match:
                            time_match = match.group()
                            break
                    
                    # Look for date/time in nearby lines if not found
                    if not date_match or not time_match:
                        # Check context (previous and next lines)
                        line_idx = lines.index(line)
                        context_lines = []
                        for i in range(max(0, line_idx-2), min(len(lines), line_idx+3)):
                            context_lines.append(lines[i])
                        
                        context = ' '.join(context_lines)
                        
                        if not date_match:
                            for date_pattern in self.date_patterns:
                                match = re.search(date_pattern, context)
                                if match:
                                    date_match = match.group()
                                    break
                        
                        if not time_match:
                            for time_pattern in self.time_patterns:
                                match = re.search(time_pattern, context)
                                if match:
                                    time_match = match.group()
                                    break
                    
                    # Clean and normalize
                    if date_match:
                        date_match = self.normalize_date(date_match)
                    if time_match:
                        time_match = self.normalize_time(time_match)
                    
                    events.append({
                        'Event': event_name,
                        'Date': date_match or 'N/A',
                        'Time': time_match or 'N/A'
                    })
                    break
        
        return events

    def clean_event_name(self, line, pattern):
        """Clean and extract event name from line"""
        # Remove extra whitespace and common prefixes/suffixes
        line = re.sub(r'\s+', ' ', line).strip()
        
        # Try to extract just the event name
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            event_name = match.group()
            return event_name.title()
        
        return line.title()

    def create_structured_pdf(self, events, output_path):
        """Create a structured PDF with the extracted events"""
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.darkblue,
            alignment=1  # Center alignment
        )
        title = Paragraph("Extracted Events Timeline", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        if not events:
            no_data = Paragraph("No events found in the PDF.", styles['Normal'])
            story.append(no_data)
        else:
            # Create table data
            table_data = [['Event', 'Date', 'Time']]  # Headers
            
            for event in events:
                table_data.append([
                    event['Event'],
                    event['Date'],
                    event['Time']
                ])
            
            # Create table
            table = Table(table_data, colWidths=[3*inch, 1.5*inch, 1*inch])
            
            # Style the table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            
            story.append(table)
        
        # Build PDF
        doc.build(story)
        print(f"Structured PDF created: {output_path}")

    def save_to_excel(self, events, output_path):
        """Save events to Excel file"""
        df = pd.DataFrame(events)
        df.to_excel(output_path, index=False)
        print(f"Excel file created: {output_path}")

    def process_pdf(self, input_pdf_path, output_dir="output"):
        """Main function to process PDF and create structured output"""
        if not os.path.exists(input_pdf_path):
            print(f"Error: File {input_pdf_path} not found!")
            return
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Processing: {input_pdf_path}")
        
        # Extract text
        text = self.extract_text_from_pdf(input_pdf_path)
        if not text:
            print("No text could be extracted from the PDF!")
            return
        
        # Extract events
        events = self.extract_events(text)
        
        if not events:
            print("No events found in the PDF!")
            return
        
        print(f"Found {len(events)} events:")
        for event in events:
            print(f"  - {event['Event']} | {event['Date']} | {event['Time']}")
        
        # Generate output files
        base_name = os.path.splitext(os.path.basename(input_pdf_path))[0]
        
        # Create structured PDF
        pdf_output = os.path.join(output_dir, f"{base_name}_structured.pdf")
        self.create_structured_pdf(events, pdf_output)
        
        # Create Excel file
        excel_output = os.path.join(output_dir, f"{base_name}_events.xlsx")
        self.save_to_excel(events, excel_output)
        
        return events

def main():
    """Main function to run the script"""
    extractor = PDFEventExtractor()
    
    # Get input file from user
    if len(sys.argv) > 1:
        input_pdf = sys.argv[1]
    else:
        input_pdf = input("Enter the path to your PDF file: ").strip()
    
    # Process the PDF
    events = extractor.process_pdf(input_pdf)
    
    if events:
        print("\n" + "="*50)
        print("SUCCESS! Structured files created in 'output' directory:")
        print("- PDF: Contains formatted table of events")
        print("- Excel: Contains events data for further analysis")
        print("="*50)

if __name__ == "__main__":
    main()

# Example usage in script:
# extractor = PDFEventExtractor()
# events = extractor.process_pdf("input.pdf")

# Requirements to install:
"""
pip install PyPDF2 pdfplumber pandas reportlab openpyxl
"""

# Usage instructions:
"""
1. Save this script as 'pdf_event_extractor.py'
2. Install required packages: pip install PyPDF2 pdfplumber pandas reportlab openpyxl
3. Run: python pdf_event_extractor.py your_file.pdf
   OR
   Run: python pdf_event_extractor.py
   Then enter the file path when prompted

The script will:
- Extract text from up to 30 pages
- Find events, dates, and times
- Create a structured PDF with a clean table
- Create an Excel file for data analysis
- Handle messy, scanned, and normal PDFs
"""