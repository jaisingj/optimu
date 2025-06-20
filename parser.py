# unified_parser.py
import pandas as pd
import io
import re

def parse_amount(val):
    if pd.isna(val):
        return 0.0
    txt = str(val).replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    nums = re.findall(r"[+-]?\d+(?:\.\d+)?", txt)
    return sum(float(n) for n in nums) if nums else 0.0

def parse_schwab_to_robinhood(file_like):
    df = pd.read_csv(file_like)
    df = df[df["Action"].isin(["Sell to Open", "Buy to Close"])]
    df["Instrument"] = df["Symbol"].str.split().str[0]
    df["Trans Code"] = df["Action"].map({"Sell to Open": "STO", "Buy to Close": "BTC"})
    df["Activity Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Price"] = df["Price"].apply(parse_amount)
    df["Amount"] = df["Amount"].apply(parse_amount)
    df["Quantity"] = df["Quantity"].abs()
    df["Process Date"] = df["Activity Date"].dt.strftime("%-m/%-d/%y")
    df["Activity Date"] = df["Activity Date"].dt.strftime("%-m/%-d/%y")
    df["Settle Date"] = ""
    return df[["Activity Date", "Process Date", "Settle Date", "Instrument", "Description", "Trans Code", "Quantity", "Price", "Amount"]].copy()

def parse_robinhood_file(file_like):
    df = pd.read_csv(file_like)
    df.columns = df.columns.str.strip()
    df["Activity Date"] = pd.to_datetime(df["Activity Date"], errors="coerce")
    df["Settle Date"] = pd.to_datetime(df.get("Settle Date"), errors="coerce")
    df["Process Date"] = df["Activity Date"].dt.strftime("%-m/%-d/%y")
    df["Activity Date"] = df["Activity Date"].dt.strftime("%-m/%-d/%y")
    df["Settle Date"] = df["Settle Date"].dt.strftime("%-m/%-d/%y")
    df["Quantity"] = df["Quantity"].abs()
    df["Price"] = df["Price"].apply(parse_amount)
    df["Amount"] = df["Amount"].apply(parse_amount)
    return df[["Activity Date", "Process Date", "Settle Date", "Instrument", "Description", "Trans Code", "Quantity", "Price", "Amount"]].copy()

def parse_fidelity_file(f_cleaned_stream):
    df = pd.read_csv(f_cleaned_stream)
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    df["Activity Date"] = pd.to_datetime(df["Run Date"], errors="coerce")
    df["Settle Date"] = pd.to_datetime(df["Settlement Date"], errors="coerce")
    df = df[df["Activity Date"].notna()].copy()
    df["Activity Date"] = df["Activity Date"].dt.strftime("%-m/%-d/%y")
    df["Settle Date"] = df["Settle Date"].dt.strftime("%-m/%-d/%y")
    df["Process Date"] = df["Activity Date"]
    df["Trans Code"] = df["Action"].str.extract(r"YOU\s+(\w+)", expand=False).str.upper()
    df["Trans Code"] = df["Trans Code"].replace({"SOLD": "STO", "BOUGHT": "BTC"})
    df["Instrument"] = df["Description"].str.extract(r"\((\w+)\)")
    df["Quantity"] = df["Quantity"].abs()
    df["Price"] = df["Price ($)"].apply(parse_amount)
    df["Amount"] = df["Amount ($)"].apply(parse_amount)
    return df[["Activity Date", "Process Date", "Settle Date", "Instrument", "Description", "Trans Code", "Quantity", "Price", "Amount"]].copy()

def get_parser_from_filename(filename, cleaned_content=None):
    if filename.startswith("Designated"):
        return parse_schwab_to_robinhood
    elif filename.startswith("History") and cleaned_content is not None:
        return lambda _: parse_fidelity_file(cleaned_content)
    else:
        return parse_robinhood_file
