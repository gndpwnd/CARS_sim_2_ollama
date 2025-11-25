#!/usr/bin/env python3
"""
Documentation Ingestion System
Ingests project documentation into PostgreSQL for LLM context retrieval.
"""
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

try:
    from postgresql_store import add_log
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("[DOC_INGEST] PostgreSQL not available")


class DocumentationIngestor:
    """Ingest and manage project documentation for LLM context"""
    
    def __init__(self, docs_directory: str = "./docs"):
        self.docs_dir = Path(docs_directory)
        self.supported_extensions = ['.md', '.txt', '.rst']
        
    def ingest_all_docs(self) -> Dict[str, Any]:
        """
        Ingest all documentation files from docs directory.
        
        Returns:
            Summary of ingestion results
        """
        if not POSTGRESQL_AVAILABLE:
            return {"error": "PostgreSQL not available"}
        
        if not self.docs_dir.exists():
            return {"error": f"Documentation directory not found: {self.docs_dir}"}
        
        results = {
            "total_files": 0,
            "ingested": 0,
            "failed": 0,
            "files": []
        }
        
        # Find all documentation files
        doc_files = []
        for ext in self.supported_extensions:
            doc_files.extend(self.docs_dir.rglob(f"*{ext}"))
        
        results["total_files"] = len(doc_files)
        
        # Ingest each file
        for doc_file in doc_files:
            try:
                if self.ingest_file(doc_file):
                    results["ingested"] += 1
                    results["files"].append(str(doc_file))
                else:
                    results["failed"] += 1
            except Exception as e:
                print(f"[DOC_INGEST] Failed to ingest {doc_file}: {e}")
                results["failed"] += 1
        
        return results
    
    def ingest_file(self, filepath: Path) -> bool:
        """
        Ingest a single documentation file.
        
        Args:
            filepath: Path to documentation file
            
        Returns:
            True if successful, False otherwise
        """
        if not POSTGRESQL_AVAILABLE:
            return False
        
        try:
            # Read file content
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Skip empty files
            if not content.strip():
                return False
            
            # Extract metadata
            filename = filepath.name
            relative_path = str(filepath.relative_to(self.docs_dir))
            
            # Determine document type
            doc_type = self._classify_document(filename, content)
            
            # Split large documents into chunks
            chunks = self._chunk_document(content, chunk_size=2000)
            
            # Ingest each chunk
            for i, chunk in enumerate(chunks):
                metadata = {
                    "source": "documentation",
                    "message_type": "documentation",
                    "doc_type": doc_type,
                    "filename": filename,
                    "filepath": relative_path,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Add to database
                add_log(chunk, metadata)
            
            print(f"[DOC_INGEST] ✅ Ingested: {relative_path} ({len(chunks)} chunks)")
            return True
            
        except Exception as e:
            print(f"[DOC_INGEST] ❌ Error ingesting {filepath}: {e}")
            return False
    
    def _classify_document(self, filename: str, content: str) -> str:
        """Classify document type based on filename and content"""
        filename_lower = filename.lower()
        content_lower = content.lower()
        
        # Architecture documentation
        if any(word in filename_lower for word in ['architecture', 'design', 'system']):
            return "architecture"
        
        # API documentation
        if any(word in filename_lower for word in ['api', 'endpoint', 'rest']):
            return "api"
        
        # Requirements documentation
        if any(word in filename_lower for word in ['requirements', 'specs', 'specification']):
            return "requirements"
        
        # User guide
        if any(word in filename_lower for word in ['guide', 'tutorial', 'howto', 'manual']):
            return "guide"
        
        # README
        if 'readme' in filename_lower:
            return "readme"
        
        # Default to general
        return "general"
    
    def _chunk_document(self, content: str, chunk_size: int = 2000) -> List[str]:
        """
        Split document into chunks for better embedding.
        
        Args:
            content: Document content
            chunk_size: Maximum characters per chunk
            
        Returns:
            List of content chunks
        """
        # Split by paragraphs first
        paragraphs = content.split('\n\n')
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            # If single paragraph is larger than chunk_size, split it
            if para_size > chunk_size:
                # Add current chunk if not empty
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split large paragraph by sentences
                sentences = para.split('. ')
                temp_chunk = []
                temp_size = 0
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    sentence_size = len(sentence)
                    
                    if temp_size + sentence_size > chunk_size and temp_chunk:
                        chunks.append('. '.join(temp_chunk) + '.')
                        temp_chunk = []
                        temp_size = 0
                    
                    temp_chunk.append(sentence)
                    temp_size += sentence_size
                
                if temp_chunk:
                    chunks.append('. '.join(temp_chunk) + '.')
            
            # Normal paragraph handling
            elif current_size + para_size > chunk_size:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size
        
        # Add remaining chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def create_system_overview_doc(self) -> bool:
        """
        Create a system overview document for the LLM.
        This serves as the primary context about what the system does.
        """
        overview = """# Multi-Agent GPS Simulation System Overview

## System Purpose
This is a multi-agent GPS denial detection and mitigation simulation system. The primary goals are:

1. **Alert Fatigue Reduction**: Use AI to intelligently filter and prioritize alerts from multiple agents
2. **Situational Awareness**: Provide operators with clear understanding of agent status and mission progress
3. **Autonomous Recovery**: Allow agents to autonomously recover from GPS jamming using last known positions
4. **Mission Planning**: Help operators make informed decisions about agent movement and mission execution

## Key Components

### Agents
- Multiple autonomous agents operating in a 2D coordinate system
- Each agent has a mission to reach a defined endpoint
- Agents can experience GPS jamming/denial in certain zones
- Agents track their last safe (unjammed) position for recovery

### Jamming Zones
- Defined areas where GPS signals are degraded or denied
- Affects agent navigation and communication quality
- Agents must navigate around or recover from jamming

### Data Storage (Hybrid System)
- **PostgreSQL**: Stores messages, errors, conversation history, and documentation
- **Qdrant**: Stores time-series telemetry data (positions, NMEA messages, GPS metrics)
- **RAG System**: Retrieves relevant context from both databases for LLM queries

### LLM Assistant (You)
Your role is to:
1. Monitor agent status and identify issues
2. Provide concise summaries when asked
3. Suggest movement commands when agents are stuck
4. Generate reports analyzing simulation performance
5. Answer operator questions about agent behavior

## Command Types You Can Handle

### Movement Commands
- "move agent1 to 5, 10" - Move single agent
- "move agent1 to 5,10 and agent2 to -3,7" - Move multiple agents

### Information Queries
- "what's the status?" - Get current state
- "what's happening with agent2?" - Agent-specific info
- "are any agents jammed?" - Situation assessment

### Reports
- "generate a report" - Detailed analysis
- "status" - Quick overview

## Best Practices for Responses

1. **Be Concise**: Operators are busy. Give direct answers.
2. **Be Actionable**: Suggest specific commands when needed.
3. **Prioritize Critical Issues**: GPS jamming and blocked agents need immediate attention.
4. **Use Data**: Reference actual positions, error counts, and communication quality.
5. **Avoid Report Loops**: Don't generate full reports unless explicitly asked.

## Coordinate System
- X Range: -50 to 50
- Y Range: -50 to 50
- Mission Endpoint: Typically at (40, 40)
- Agents start near origin and must navigate to endpoint

## Communication Quality
- 1.0 = Perfect GPS, no jamming
- 0.5-0.9 = Degraded GPS
- 0.0-0.4 = Severe jamming, GPS denied
- Jammed agents should return to last safe position before proceeding
"""
        
        try:
            metadata = {
                "source": "documentation",
                "message_type": "documentation",
                "doc_type": "system_overview",
                "filename": "SYSTEM_OVERVIEW.md",
                "priority": "high",
                "timestamp": datetime.now().isoformat()
            }
            
            add_log(overview, metadata)
            print("[DOC_INGEST] ✅ Created system overview document")
            return True
            
        except Exception as e:
            print(f"[DOC_INGEST] ❌ Failed to create overview: {e}")
            return False


def ingest_documentation():
    """Main entry point for documentation ingestion"""
    print("="*60)
    print("DOCUMENTATION INGESTION")
    print("="*60)
    
    ingestor = DocumentationIngestor()
    
    # Create system overview first
    print("\n[1/2] Creating system overview...")
    ingestor.create_system_overview_doc()
    
    # Ingest all documentation files
    print("\n[2/2] Ingesting documentation files...")
    results = ingestor.ingest_all_docs()
    
    print("\n" + "="*60)
    print("INGESTION COMPLETE")
    print("="*60)
    print(f"Total files found: {results.get('total_files', 0)}")
    print(f"Successfully ingested: {results.get('ingested', 0)}")
    print(f"Failed: {results.get('failed', 0)}")
    
    if results.get('files'):
        print("\nIngested files:")
        for f in results['files']:
            print(f"  - {f}")
    
    return results


if __name__ == "__main__":
    ingest_documentation()