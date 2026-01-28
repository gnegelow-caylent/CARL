#!/bin/bash
# Build Lambda deployment packages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build"

echo "Building CARL Lambda packages..."

# Clean previous builds
rm -rf "$DIST_DIR" "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

# Install dependencies to build directory
echo "Installing dependencies..."
pip install -r "$PROJECT_ROOT/requirements.txt" -t "$BUILD_DIR/python" --quiet

# Copy source code
echo "Copying source code..."
cp -r "$PROJECT_ROOT/src" "$BUILD_DIR/python/"

# Create deployment packages for each handler
HANDLERS=("slack_router" "findings_processor")

for handler in "${HANDLERS[@]}"; do
    echo "Building $handler package..."

    PACKAGE_DIR="$BUILD_DIR/$handler"
    mkdir -p "$PACKAGE_DIR"

    # Copy dependencies and source
    cp -r "$BUILD_DIR/python/"* "$PACKAGE_DIR/"

    # Create handler wrapper
    cat > "$PACKAGE_DIR/${handler}.py" << EOF
# Lambda handler wrapper for $handler
from src.handlers.${handler} import handler
EOF

    # Create ZIP package
    cd "$PACKAGE_DIR"
    zip -r "$DIST_DIR/${handler}.zip" . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*" --quiet
    cd "$PROJECT_ROOT"

    echo "Created $DIST_DIR/${handler}.zip"
done

# Create combined package (all handlers)
echo "Building combined package..."
cd "$BUILD_DIR/python"
zip -r "$DIST_DIR/carl-app.zip" . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*" --quiet
echo "Created $DIST_DIR/carl-app.zip"

# Clean up build directory
rm -rf "$BUILD_DIR"

echo ""
echo "Build complete! Packages:"
ls -lh "$DIST_DIR"
