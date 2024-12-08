from fastapi import FastAPI, HTTPException
# from weasyprint import HTML, CSS
#from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import tempfile
from datetime import datetime
import json

class PDFGenerator:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.env = Environment(loader=FileSystemLoader("templates"))

    async def generate_memory_pdf(self, memories):
        try:
            # Load the HTML template
            template = self.env.get_template("memories_template.html")

            # Group memories by year
            memories_by_year = {}
            for memory in memories:
                year = datetime.strptime(memory.time_period, "%Y-%m-%d").year
                if year not in memories_by_year:
                    memories_by_year[year] = []
                memories_by_year[year].append(memory)

            # Sort years in descending order
            sorted_years = sorted(memories_by_year.keys(), reverse=True)

            # Render HTML
            html_content = template.render(
                memories_by_year=memories_by_year,
                sorted_years=sorted_years,
                category_config=CATEGORY_CONFIG,
                format_date=lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%B %d, %Y")
            )

            # Create PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
                HTML(string=html_content).write_pdf(
                    pdf_file.name,
                    stylesheets=[CSS(string=self.get_pdf_styles())]
                )

                # Upload to Supabase
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"pdfs/memories_{timestamp}.pdf"

                with open(pdf_file.name, 'rb') as f:
                    self.supabase.storage.from_("exports").upload(
                        file_path,
                        f.read(),
                        file_options={"content-type": "application/pdf"}
                    )

                # Get public URL
                public_url = self.supabase.storage.from_("exports").get_public_url(file_path)
                return {"pdf_url": public_url}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    def get_pdf_styles(self):
        return """
            @page {
                margin: 2.5cm;
                @top-center {
                    content: "Memory Journey";
                    font-family: Arial;
                    font-size: 10pt;
                    color: #666;
                }
                @bottom-center {
                    content: "Page " counter(page) " of " counter(pages);
                    font-family: Arial;
                    font-size: 10pt;
                    color: #666;
                }
            }

            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }

            .year-section {
                margin-bottom: 2em;
                page-break-inside: avoid;
            }

            .year-header {
                font-size: 24pt;
                color: #2196F3;
                margin-bottom: 1em;
                border-bottom: 2px solid #2196F3;
            }

            .memory-card {
                margin-bottom: 2em;
                padding: 1em;
                border: 1px solid #ddd;
                border-radius: 8px;
                page-break-inside: avoid;
            }

            .memory-header {
                display: flex;
                align-items: center;
                margin-bottom: 1em;
            }

            .memory-date {
                font-size: 14pt;
                color: #666;
            }

            .category-tag {
                padding: 4px 8px;
                border-radius: 4px;
                color: white;
                font-size: 10pt;
                margin-left: 1em;
            }

            .memory-content {
                margin-bottom: 1em;
            }

            .memory-images {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 1em;
                margin-bottom: 1em;
            }

            .memory-image {
                width: 100%;
                height: auto;
                border-radius: 4px;
            }

            .emotions-container {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5em;
            }

            .emotion-tag {
                padding: 2px 6px;
                border-radius: 4px;
                background-color: #f0f0f0;
                font-size: 10pt;
            }

            @media print {
                .memory-images {
                    break-inside: avoid;
                }
            }
        """
