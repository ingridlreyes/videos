"""Tests for the real pipeline without invoking billable Azure APIs."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_pipeline import parse_model_json,related_text,run_pipeline

class PipelineTests(unittest.TestCase):
    """Ensure no fabricated steps, valid JSON, and correct speaker filtering."""
    def test_model_output_validation(self):
        """Accept grounded structured steps and reject unsupported response shapes."""
        self.assertEqual(parse_model_json('{"steps":[]}'),{'steps':[]})
        with self.assertRaises(ValueError):parse_model_json('{"foo":1}')
    def test_filter_instructor(self):
        """Exclude questions spoken by other labeled participants."""
        seg=[{'start':2,'end':4,'speaker':'Ana','text':'Pregunta'}, {'start':3,'end':5,'speaker':'Profe','text':'Seleccionar Crear'}]
        txt=related_text(seg,4,main_speaker='Profe')
        self.assertIn('Seleccionar Crear',txt)
        self.assertNotIn('Pregunta',txt)
    def test_no_model_no_fabricated_pptx(self):
        """Offline extraction must not fake a PowerPoint from unidentified steps."""
        root=Path(__file__).resolve().parents[1]
        result=run_pipeline(str(root/'assets/video_demo_ficticio.mp4'),use_ai=False,limit_minutes=1,max_frames=5)
        self.assertEqual(result['status'],'needs_review')
        self.assertIsNone(result['pptx'])

if __name__=='__main__':unittest.main()
