# Professional PDF Report Generation

## Overview

CARL now generates professional, auditor-ready PDF reports instead of plain Markdown files.

## Features

✅ **Professional Design**
- Clean, modern layout inspired by consulting firm reports
- Color-coded severity indicators
- Professional typography and spacing
- Page numbers and footers

✅ **Visual Charts**
- Compliance score gauge (0-100%)
- Findings by severity bar chart
- Trend analysis line charts (when historical data available)
- All charts embedded as PNG images

✅ **Structured Content**
- Cover page with audit period and organization
- Executive summary with key metrics
- Control assessment table with pass/fail status
- Detailed findings section with remediation steps
- Professional color palette (blues, grays, greens, reds)

✅ **Auditor-Ready**
- PDF format (universally accepted)
- Table of contents
- Proper headers and footers
- Professional appearance

## Technical Implementation

**PDF Generation:** WeasyPrint (HTML → PDF)
**Charts:** Matplotlib (PNG embedded as base64)
**Design:** HTML5 + CSS3 with print styles
**Storage:** S3 with presigned URLs

## Lambda Layer Requirements ⚠️

**IMPORTANT:** WeasyPrint requires system libraries that aren't available in standard Lambda runtime.

### Option 1: Lambda Layer (Recommended)

Create a Lambda Layer with WeasyPrint dependencies:

```bash
# Use Amazon Linux 2 Docker container (matches Lambda runtime)
docker run --rm -v $(pwd):/output amazonlinux:2 bash -c "
    yum install -y \
        cairo cairo-devel \
        pango pango-devel \
        gdk-pixbuf2-devel \
        libffi-devel \
        python3-devel \
        gcc \
        python3-pip

    pip3 install \
        weasyprint==60.0 \
        matplotlib==3.8.0 \
        pillow==10.0.0 \
        -t /output/python

    # Copy system libraries
    mkdir -p /output/lib
    cp -r /usr/lib64/{libcairo*,libpango*,libgdk*,libffi*} /output/lib/
"

# Zip the layer
cd $(pwd)
zip -r weasyprint-layer.zip python lib

# Upload to AWS Lambda Layer
aws lambda publish-layer-version \
    --layer-name weasyprint-dependencies \
    --zip-file fileb://weasyprint-layer.zip \
    --compatible-runtimes python3.11 python3.12
```

### Option 2: Docker Lambda (Alternative)

If Lambda Layer doesn't work, use Docker Lambda with custom image:

```dockerfile
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies
RUN yum install -y cairo pango gdk-pixbuf2 libffi

# Install Python packages
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy function code
COPY carl-app/src ${LAMBDA_TASK_ROOT}

CMD ["handlers.slack_router.lambda_handler"]
```

### Option 3: External Service (Simple)

If Lambda proves difficult, use external PDF service:
- **gotenberg** (open source, self-hosted)
- **DocRaptor** (SaaS, $0.004/PDF)
- **PDFShift** (SaaS, $0.01/PDF)

**Cost comparison:**
- Lambda Layer: Free (included in Lambda pricing)
- Docker Lambda: Free (included in Lambda pricing)
- External service: ~$1-5/month for 100-500 reports

## Testing Locally

```bash
# Install system dependencies (macOS)
brew install cairo pango gdk-pixbuf libffi

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev

# Install Python packages
pip install -r requirements.txt

# Test PDF generation
python -c "
from services.pdf_generator import PDFReportGenerator
gen = PDFReportGenerator()
pdf = gen.generate_pdf({
    'report_type': 'Test Report',
    'compliance_score': 85,
    'findings_by_severity': {'critical': 2, 'high': 5, 'medium': 12, 'low': 8}
})
with open('test_report.pdf', 'wb') as f:
    f.write(pdf)
print('PDF generated: test_report.pdf')
"
```

## Deployment Steps

1. **Install dependencies locally** (for testing)
   ```bash
   cd /Users/gnegelow/Documents/CARL/carl-app
   pip install -r requirements.txt
   ```

2. **Create Lambda Layer** (follow Option 1 above)

3. **Update Terraform** (add layer to Lambda function)
   ```hcl
   resource "aws_lambda_function" "api" {
     # ... existing config ...

     layers = [
       aws_lambda_layer_version.weasyprint.arn
     ]
   }

   resource "aws_lambda_layer_version" "weasyprint" {
     layer_name          = "weasyprint-dependencies"
     s3_bucket           = "your-lambda-layers-bucket"
     s3_key              = "weasyprint-layer.zip"
     compatible_runtimes = ["python3.12"]
   }
   ```

4. **Deploy and test**
   ```bash
   cd /Users/gnegelow/Documents/CARL/carl-infrastructure/environments/dev
   terraform apply

   # Test in Slack
   /carl report executive
   ```

## Monitoring

**CloudWatch Logs:**
- Look for "Generated PDF report (X bytes)" messages
- Check for WeasyPrint import errors
- Monitor Lambda memory usage (PDFs may need more memory)

**Expected Performance:**
- Executive summary: ~2-3 seconds
- Full audit report: ~5-8 seconds
- PDF size: 500KB - 2MB (depending on findings count)

## Troubleshooting

### Error: "No module named 'cairo'"
- **Cause:** System libraries not available
- **Fix:** Install Lambda Layer (Option 1) or use Docker Lambda (Option 2)

### Error: "ModuleNotFoundError: No module named 'weasyprint'"
- **Cause:** Package not installed
- **Fix:** Run `pip install -r requirements.txt`

### PDF looks wrong/broken
- **Cause:** CSS not rendering properly
- **Fix:** Check WeasyPrint version (needs >=60.0)

### Lambda timeout
- **Cause:** PDF generation taking too long
- **Fix:** Increase Lambda timeout to 60s, increase memory to 512MB

## Future Enhancements

- [ ] Add trend analysis charts (compliance score over time)
- [ ] Control-specific PDF reports (currently markdown fallback)
- [ ] Custom branding (logo, colors, fonts)
- [ ] Multiple report templates (executive, technical, auditor)
- [ ] Report scheduling (weekly/monthly auto-generation)
- [ ] Email delivery (send PDF directly to stakeholders)
- [ ] Historical comparison (side-by-side reports)

## Cost Estimate

**Lambda Layer approach:**
- PDF generation: ~$0.05/month (included in Lambda pricing)
- S3 storage: ~$0.50/month (PDF files)
- **Total: ~$0.55/month**

**External service approach:**
- 100 reports/month: ~$1-5/month
- S3 storage: ~$0.50/month
- **Total: ~$1.50-5.50/month**

**Recommendation:** Use Lambda Layer for cost efficiency and full control.
