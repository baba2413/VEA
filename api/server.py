import os
import tempfile
from flask import Flask, request, send_from_directory, jsonify, Response
from werkzeug.utils import secure_filename

from .gemini_test import analyze_video_with_gemini


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WEB_DIR = os.path.join(ROOT_DIR, 'web')


app = Flask(
    __name__,
    static_folder=WEB_DIR,
    static_url_path=''
)


@app.after_request
def add_cors_headers(resp: Response) -> Response:
    # Allow cross-origin requests for API endpoints during local development
    try:
        path = request.path or ''
    except Exception:
        path = ''
    if path.startswith('/api/'):
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Vary'] = 'Origin'
    return resp


@app.get('/')
def root() -> Response:
    return send_from_directory(WEB_DIR, 'index.html')


@app.get('/favicon.ico')
def favicon() -> Response:
    # Avoid noisy 404s in the browser console
    return Response(status=204)


@app.post('/api/analyze/summary')
def analyze_summary() -> Response:
    """Handle summary analysis.

    Accepts multipart/form-data with fields:
      - video: the uploaded video file
      - requirements: optional text to adjust predefined prompt
    """
    if 'video' not in request.files:
        return jsonify({
            'error': 'missing_video',
            'message': '비디오 파일이 필요합니다.'
        }), 400

    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({
            'error': 'empty_filename',
            'message': '파일명을 확인하세요.'
        }), 400

    requirements = (request.form.get('requirements') or '').strip()

    filename = secure_filename(video_file.filename)
    suffix = os.path.splitext(filename)[1] or '.mp4'

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            video_file.save(tmp)
            tmp_path = tmp.name

        # If no requirements provided, pass None to use default hardcoded prompt
        prompt_to_use = requirements if requirements else None
        result_text = analyze_video_with_gemini(tmp_path, prompt=prompt_to_use)

        return Response(result_text, mimetype='text/plain; charset=utf-8')

    except Exception as e:  # pragma: no cover - simple error surface
        return jsonify({
            'error': 'analysis_failed',
            'message': str(e)
        }), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def main() -> None:
    # Bind to 0.0.0.0 for local network testing; debug off by default
    app.run(host='0.0.0.0', port=5000, debug=True)


if __name__ == '__main__':
    main()


