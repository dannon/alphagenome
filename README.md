# AlphaGenome Galaxy Tools Project

## Overview

This project integrates Google DeepMind's AlphaGenome model into the Galaxy bioinformatics platform, providing powerful AI-driven genomic analysis tools for the research community.

## Project Structure

```
alphagenome/
├── README.md                              # This file
├── implementation_roadmap.md              # Quick reference and implementation order
├── alphagenome_galaxy_prd.md             # Phase 1 PRDs (Variant Scorer, Regulatory Discovery)
├── alphagenome_phase2_prds.md            # Phase 2 PRDs (Expression, Splicing, Design tools)
├── technical_implementation_guide.md      # Technical details and best practices
├── alphagenome_variant_scorer_tool.xml   # Example Galaxy tool wrapper
├── alphagenome_variant_scorer.py         # Example Python implementation
└── .env                                   # Environment variables (API keys, etc.)
```

## Tools Overview

### Phase 1 - Core Tools
1. **Variant Effect Prediction Tool** - Annotate VCF files with functional impact predictions
2. **Regulatory Element Discovery Workflow** - Identify and characterize regulatory regions

### Phase 2 - Quick Wins
3. **Gene Expression Prediction Tool** - Predict tissue-specific expression from sequences
4. **Splicing Pattern Analysis Tool** - Analyze splicing effects of variants
5. **Synthetic Biology Design Assistant** - AI-guided promoter optimization

## Getting Started

1. **Review Documentation**
   - Start with `implementation_roadmap.md` for a high-level overview
   - Read the relevant PRD for the tool you're implementing
   - Consult `technical_implementation_guide.md` for coding patterns

2. **Set Up Development Environment**
   ```bash
   # Install dependencies
   pip install planemo galaxy-tool-util
   pip install alphagenome pysam cyvcf2
   
   # Clone Galaxy for local testing
   git clone https://github.com/galaxyproject/galaxy.git
   ```

3. **Get AlphaGenome API Key**
   - Visit https://deepmind.google.com/science/alphagenome
   - Request API access
   - Store key securely in `.env` file

4. **Start Implementation**
   - Begin with the Variant Effect Prediction Tool
   - Use `alphagenome_variant_scorer.py` as a template
   - Test locally with planemo before Galaxy integration

## Implementation Tips

### For Claude Code

When implementing with Claude Code, provide these key pieces:
1. The relevant PRD for the tool
2. The technical implementation guide sections
3. The Python template as a starting point
4. Any specific Galaxy requirements

### Best Practices
- Always implement caching to minimize API calls
- Handle rate limiting gracefully
- Stream large files rather than loading into memory
- Provide clear progress feedback to users
- Include comprehensive error handling

## Quick Commands

```bash
# Test a tool locally
planemo test tools/alphagenome_variant_scorer/

# Serve tool with Galaxy
planemo serve tools/alphagenome_variant_scorer/

# Lint tool XML
planemo lint tools/alphagenome_variant_scorer/

# Create tool tests
planemo test --update_test_data tools/alphagenome_variant_scorer/
```

## API Considerations

- **Rate Limits**: The AlphaGenome API is suitable for thousands, not millions of predictions
- **Non-commercial Use**: These tools are for research use only
- **Caching**: Implement aggressive caching to avoid redundant API calls
- **Batch Processing**: Group requests efficiently to minimize API calls

## Testing Strategy

1. **Unit Tests**: Test individual functions
2. **Integration Tests**: Test with mock API responses
3. **Galaxy Tests**: Use planemo for tool testing
4. **End-to-End Tests**: Test complete workflows with real data

## Support Resources

- **AlphaGenome Documentation**: https://www.alphagenomedocs.com/
- **Galaxy Training**: https://training.galaxyproject.org/
- **Galaxy Help**: https://help.galaxyproject.org/
- **Tool Development**: https://docs.galaxyproject.org/en/latest/dev/

## Contributing

1. Follow Galaxy tool development best practices
2. Include comprehensive documentation
3. Add tests for all new functionality
4. Ensure tools work with standard Galaxy datatypes
5. Consider adding example workflows

## License

These tools are for non-commercial research use only, in accordance with AlphaGenome's terms of service.

## Next Steps

1. Review all documentation files
2. Set up your development environment
3. Start with the Variant Effect Prediction Tool
4. Test thoroughly before moving to the next tool
5. Share your progress and get feedback early

Good luck with the implementation! 🚀
