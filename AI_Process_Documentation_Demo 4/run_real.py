"""Command-line entry point: analyze an MP4 and create a PPTX/DOCX from REAL evidence."""
import argparse,json
from real_pipeline import run_pipeline

def main():
    """Parse flags and run pipeline; print machine-readable paths for the outputs."""
    p=argparse.ArgumentParser(description='Video real a PowerPoint editable')
    p.add_argument('--video',required=True,help='Ruta al archivo MP4')
    p.add_argument('--transcript',help='VTT Teams / JSON normalizado opcional')
    p.add_argument('--speaker',default='',help='Identificador del instructor en la transcripción')
    p.add_argument('--rules',default='',help='Reglas específicas de extracción')
    p.add_argument('--limit-minutes',type=int,default=6)
    p.add_argument('--max-frames',type=int,default=20)
    p.add_argument('--no-ai',action='store_true',help='Solo validar extracción, no inventar pasos')
    args=p.parse_args()
    result=run_pipeline(args.video,args.transcript,args.speaker,args.rules,not args.no_ai,args.limit_minutes,args.max_frames)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
