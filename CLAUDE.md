# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`meta_genie` is an academic literature screening automation system for meta-analysis research. It uses rule-based keyword filtering to analyze paper titles and abstracts, automatically classifying whether studies should be included in the research based on specific criteria (depression, mobile/digital, behavioral activation). The system includes a Streamlit web interface for human review and final decision-making.

## Development Commands

### Core Pipeline
```bash
# Run the main rule-based filtering pipeline
python pipeline_runner_rule.py

# Run LLM secondary filtering on rule-based exclude results
python llm_secondary_filter.py

# Run complete hybrid pipeline (rule-based + LLM secondary)
python pipeline_hybrid_filter.py

# Launch the Streamlit review interface
streamlit run streamlit_keyword_review.py
```

### Data Processing
```bash
# Process abstract data (uses default input file abstract-depression-set.txt)
cd abstract_pharsing && python extract_abstract.py

# Or specify a custom input file
cd abstract_pharsing && python extract_abstract.py your_input_file.txt
```

## Architecture

### Main Components

1. **pipeline_runner_rule.py** - Main orchestration script that:
   - Loads data from `data/meta_article_data.csv`
   - Runs rule-based filtering through `RuleBasedKeywordFilter`
   - Saves timestamped results to `output/` directory
   - Provides detailed logging to `logs/` directory

2. **rule_based_filter.py** - Core filtering engine containing:
   - `RuleBasedKeywordFilter` class with keyword matching logic
   - Three keyword categories: depression, mobile/digital, behavioral activation
   - Support for wildcard patterns (e.g., `behavio* therap*`)
   - Word boundary matching for precise keyword detection

3. **streamlit_keyword_review.py** - Web interface for human review:
   - Interactive paper-by-paper review system
   - Real-time keyword highlighting in titles/abstracts
   - Multi-reviewer support with reviewer tracking
   - Progress tracking and filtering capabilities

4. **llm_secondary_filter.py** - LLM-based secondary filtering system:
   - Processes exclude cases from rule-based filtering
   - Uses GPT-4o for flexible keyword interpretation
   - Provides contextual analysis beyond rigid rules
   - Includes comprehensive logging and checkpoint system

5. **pipeline_hybrid_filter.py** - Unified hybrid filtering pipeline:
   - Combines rule-based and LLM filtering approaches
   - Automatic sequential processing pipeline
   - Generates comprehensive comparison reports
   - Provides detailed performance analytics

### Data Flow

#### Standard Rule-Based Pipeline
```
Input CSV (data/meta_article_data.csv)
    ↓
Rule-based filtering (pipeline_runner_rule.py)
    ↓
Timestamped results (rule_base_output/rule_based_results_YYYYMMDD_HHMMSS.csv)
    ↓
Human review (streamlit_keyword_review.py)
    ↓
Final reviewed results (same CSV with human_* columns)
```

#### Hybrid Pipeline (Rule-based + LLM)
```
Input CSV (data/meta_article_data.csv)
    ↓
Rule-based filtering (RuleBasedKeywordFilter)
    ↓
Rule-based results (rule_base_output/)
    ↓
LLM secondary filtering on exclude cases (LLMSecondaryFilter)
    ↓
Final hybrid results (output/hybrid_final_results_YYYYMMDD_HHMMSS.csv)
    ↓
Human review (streamlit_keyword_review.py)
    ↓
Final reviewed results
```

### Key Data Structures

#### Rule-Based Results
- **Input CSV**: Must contain `Title` and `Abstract` columns
- **Rule-Based Output CSV**: Adds `depression_keywords`, `mobile_keywords`, `behavioral_keywords`, `result` columns
- **Review CSV**: Adds `human_*` columns for reviewer decisions, `reviewer_name`, `review_status`, `review_date`

#### Hybrid Results (Rule-based + LLM)
- **Hybrid Output CSV**: Contains both rule-based and LLM results:
  - `rule_depression_keywords`, `rule_mobile_keywords`, `rule_behavioral_keywords`, `rule_result`
  - `llm_depression_keywords`, `llm_mobile_keywords`, `llm_behavioral_keywords`, `llm_result`
  - `llm_depression_highlight`, `llm_mobile_highlight`, `llm_behavioral_highlight`, `llm_reason`
  - `final_result`: Final classification combining both approaches

## Keywords System

### Rule-Based Filtering
The rule-based system uses strict keyword matching with three mandatory categories:
- **Depression**: `depression`, `depressive symptoms`, `depressive disorder`
- **Mobile/Digital**: `mobile application`, `smartphone`, `app`, `digital`, `mhealth`, etc.
- **Behavioral**: `behavioral activation`, `behavioural activation`, plus wildcard patterns

Papers must have keywords from ALL three categories to be included.

### LLM Secondary Filtering
The LLM system provides contextual analysis for papers excluded by rule-based filtering:
- **Flexible Interpretation**: Considers synonyms, related terms, and contextual meanings
- **Template-Based**: Uses `templates/keyword_template_en.md` for consistent evaluation
- **Conservative Approach**: Only includes papers with clear evidence of all three categories
- **Reasoning**: Provides detailed Korean explanations for decisions

### Hybrid Approach Benefits
- **Higher Recall**: LLM rescues papers missed by rigid rule matching
- **Maintained Precision**: Conservative LLM approach prevents false positives
- **Transparency**: Both rule-based and LLM reasoning are preserved
- **Efficiency**: Only exclude cases are processed by expensive LLM calls

## Code Conventions

- UTF-8 encoding handling for Korean/English mixed content
- Comprehensive logging with timestamps
- Type hints for function parameters and returns
- Pandas DataFrame operations for data processing
- Regular expressions for keyword pattern matching
- Session state management in Streamlit for multi-step workflows

## Testing

No formal test framework is configured. Verify functionality by:
1. Running the pipeline with sample data
2. Checking output file generation
3. Reviewing logs for processing statistics
4. Testing Streamlit interface with generated results

## Abstract Extraction System

### Overview
The `extract_abstract/` directory contains an advanced title-based abstract extraction system that matches academic papers from CSV metadata with full-text abstracts from raw text files.

### Components

1. **extract_by_title_matching.py** - Main extraction script:
   - Loads metadata from `data/meta_article_empty_abstract_data.csv`
   - Parses abstracts from `abstract-depression-set.txt` (1,049 sequential records)
   - Performs intelligent title matching with multiple strategies
   - Generates comprehensive CSV outputs with matching information

### Matching Strategies

The system uses sophisticated multi-level matching:

1. **Exact Matching**: Perfect title matches (normalized)
2. **Fuzzy Matching**: Similarity-based matching (threshold: 0.7)
   - String similarity using SequenceMatcher
   - Keyword-based similarity weighting
   - Stopword filtering for better accuracy
3. **Sequential Record Parsing**: 
   - Handles numbered academic abstracts (1., 2., 3...)
   - Filters out DOI confusion (avoids matching DOI numbers as paper numbers)

### Text Processing Features

- **Title Normalization**: Case-insensitive, punctuation handling
- **Keyword Extraction**: Smart filtering of academic stopwords
- **Abstract Parsing**: 
  - Author information detection and separation
  - DOI extraction across multiple lines
  - Newline-pattern-based title extraction
  - Trailing period removal from titles
- **Data Validation**: 
  - Long text field truncation (>10,000 chars)
  - CSV special character protection
  - Progress tracking for large datasets

### Usage

```bash
cd extract_abstract
python extract_by_title_matching.py
```

### Output Files

1. **title_matched_complete_YYYYMMDD_HHMMSS.csv**:
   - Complete merged dataset with all records
   - Additional columns: `Matched_Title`, `Match_Type`, `Match_Similarity`, `Match_Status`
   - Match types: 'Exact', 'Fuzzy', 'None', 'Existing'

2. **failed_matches_YYYYMMDD_HHMMSS.csv**:
   - Records that couldn't be matched automatically
   - Includes closest match suggestions for manual review
   - Additional columns: `Failure_Reason`, `Closest_Match_Title`, `Closest_Similarity`

### Performance Metrics

Recent extraction results (1,027 input records):
- **Abstract coverage**: ~99% (achieved with threshold 0.7)
- **Exact matches**: ~800 records
- **Fuzzy matches**: ~200 records  
- **Failed matches**: <20 records (requires manual review)
- **Processing time**: Real-time progress tracking per 100 records

### Data Quality Controls

- CSV quoting protection against malformed data
- Automatic detection of abnormally long text fields
- Newline character sanitization
- Warning system for data anomalies
- Duplicate title detection and handling

### Next Steps

The merged CSV file from this extraction system should be:
1. **Human reviewed** for quality assurance
2. **Manually matched** for failed cases (if appropriate)
3. **Placed in `data/` folder** as the final dataset
4. **Used for downstream meta-analysis automation**

This system bridges the gap between raw academic text files and structured metadata, enabling automated meta-analysis workflows while maintaining high data quality through human oversight.