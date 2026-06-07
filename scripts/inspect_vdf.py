import sys
import os
from unittest.mock import MagicMock

# Mock needed components to get to the point of inspecting VirtualDataFrame
mock_modules = [
    "plotly", "plotly.io", "plotly.graph_objects",
    "google", "google.cloud", "google.cloud.sql", "google.cloud.sql.connector",
    "pg8000", "IPython", "IPython.display"
]
for mod in mock_modules:
    sys.modules[mod] = MagicMock()

try:
    from pandasai import VirtualDataFrame
    print(f"Attributes of VirtualDataFrame: {dir(VirtualDataFrame)}")

    # Create a dummy one
    vdf = VirtualDataFrame(source={"type": "postgres", "table": "test", "connection": {}}, description="test")
    print(f"Attributes of vdf instance: {dir(vdf)}")

    if hasattr(vdf, "_connector"):
        print(f"Attributes of vdf._connector: {dir(vdf._connector)}")

    if hasattr(vdf, "_schema"):
        print(f"Attributes of vdf._schema: {dir(vdf._schema)}")

except Exception as e:
    print(f"Error: {e}")
