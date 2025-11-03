import os
import tempfile
from flask import Flask, request, send_from_directory, jsonify, Response
from werkzeug.utils import secure_filename

from .gemini_test import analyze_video_with_gemini
from .utils import (
    parse_gemini_analysis,
    save_analysis_result,
    get_analysis_result,
    load_analysis_results
)


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WEB_DIR = os.path.join(ROOT_DIR, 'web')
SAMPLE_VIDEOS_DIR = os.path.join(ROOT_DIR, 'sample_videos')


def validate_filename(filename: str) -> str:
    """Validate filename for safety without removing parentheses.

    Prevents path traversal but allows parentheses and other safe characters.
    """
    if not filename:
        raise ValueError("Empty filename")

    # Prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError("Invalid filename")

    # Only allow safe characters: alphanumeric, dot, dash, underscore, parentheses, space
    import re
    if not re.match(r'^[a-zA-Z0-9._\-() ]+$', filename):
        raise ValueError("Invalid filename characters")

    return filename


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


@app.get('/api/videos')
def list_videos() -> Response:
    """List all videos in the sample_videos directory."""
    try:
        if not os.path.exists(SAMPLE_VIDEOS_DIR):
            return jsonify([]), 200

        files = []
        for filename in os.listdir(SAMPLE_VIDEOS_DIR):
            if filename.startswith('.'):
                continue
            filepath = os.path.join(SAMPLE_VIDEOS_DIR, filename)
            if os.path.isfile(filepath) and filename.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                files.append({
                    'filename': filename,
                    'path': f'/api/videos/{filename}'
                })

        # Sort by filename
        files.sort(key=lambda x: x['filename'])
        return jsonify(files), 200

    except Exception as e:
        return jsonify({
            'error': 'list_failed',
            'message': str(e)
        }), 500


@app.get('/api/videos/<filename>')
def serve_video(filename: str) -> Response:
    """Serve a video file from the sample_videos directory with proper range request support."""
    try:
        safe_filename = validate_filename(filename)
        video_path = os.path.join(SAMPLE_VIDEOS_DIR, safe_filename)

        if not os.path.exists(video_path):
            return jsonify({
                'error': 'not_found',
                'message': '비디오 파일을 찾을 수 없습니다.'
            }), 404

        # Use send_from_directory with conditional=True for proper range request support
        response = send_from_directory(
            SAMPLE_VIDEOS_DIR,
            safe_filename,
            mimetype='video/mp4',
            as_attachment=False,
            conditional=True
        )

        # Ensure proper headers for video streaming
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-cache'

        return response

    except Exception as e:
        return jsonify({
            'error': 'serve_failed',
            'message': str(e)
        }), 500


@app.post('/api/analyze/video/<filename>')
def analyze_video_by_filename(filename: str) -> Response:
    """Analyze a video from sample_videos directory by filename.

    Accepts optional JSON body with:
      - requirements: optional text to adjust predefined prompt
    """
    try:
        safe_filename = validate_filename(filename)
        video_path = os.path.join(SAMPLE_VIDEOS_DIR, safe_filename)

        if not os.path.exists(video_path):
            return jsonify({
                'error': 'not_found',
                'message': '비디오 파일을 찾을 수 없습니다.'
            }), 404

        # Get optional requirements from JSON body
        requirements = ''
        if request.is_json:
            data = request.get_json()
            requirements = (data.get('requirements') or '').strip()

        # Analyze with Gemini
        prompt_to_use = requirements if requirements else None
        result_text = analyze_video_with_gemini(video_path, prompt=prompt_to_use)

        # Parse the response
        parsed_result = parse_gemini_analysis(result_text)

        # Automatically save the result
        save_analysis_result(safe_filename, parsed_result)

        return jsonify(parsed_result), 200

    except Exception as e:
        return jsonify({
            'error': 'analysis_failed',
            'message': str(e)
        }), 500


@app.get('/api/results')
def get_all_results() -> Response:
    """Get all stored analysis results."""
    try:
        results = load_analysis_results()
        return jsonify(results), 200
    except Exception as e:
        return jsonify({
            'error': 'load_failed',
            'message': str(e)
        }), 500


@app.get('/api/results/<filename>')
def get_result(filename: str) -> Response:
    """Get analysis result for a specific video file."""
    try:
        safe_filename = validate_filename(filename)
        result = get_analysis_result(safe_filename)

        if result is None:
            return jsonify({
                'error': 'not_found',
                'message': '분석 결과가 없습니다.'
            }), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'error': 'load_failed',
            'message': str(e)
        }), 500


@app.post('/api/results/<filename>')
def save_result(filename: str) -> Response:
    """Save analysis result for a specific video file.

    Expects JSON body with analysis data.
    """
    try:
        safe_filename = validate_filename(filename)

        if not request.is_json:
            return jsonify({
                'error': 'invalid_request',
                'message': 'JSON 데이터가 필요합니다.'
            }), 400

        analysis_data = request.get_json()
        save_analysis_result(safe_filename, analysis_data)

        return jsonify({
            'success': True,
            'message': '저장되었습니다.'
        }), 200

    except Exception as e:
        return jsonify({
            'error': 'save_failed',
            'message': str(e)
        }), 500


def main() -> None:
    # Bind to 0.0.0.0 for local network testing; debug off by default
    # Using port 5001 to avoid conflict with macOS AirPlay Receiver on port 5000
    app.run(host='0.0.0.0', port=5001, debug=True)


if __name__ == '__main__':
    main()


