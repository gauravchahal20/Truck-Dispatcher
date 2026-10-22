import json

def format_schema():
    with open("scripts/az4n_columns.json", "r") as f:
        cols = json.load(f)

    lines = []
    lines.append("| # | Field Name (`fieldName`) | Column Name (`name`) | Data Type (`dataTypeName`) |")
    lines.append("|---|---|---|---|")
    for i, c in enumerate(cols, 1):
        lines.append(f"| {i} | `{c['fieldName']}` | `{c['name']}` | {c['type']} |")

    table_md = "\n".join(lines)
    with open("scripts/az4n_schema_table.md", "w") as f:
        f.write(table_md)
    print(f"Generated markdown table for {len(cols)} columns in scripts/az4n_schema_table.md")

if __name__ == "__main__":
    format_schema()
