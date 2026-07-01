# ═══════════════════════════════════════════
# تنفيذ أكواد Python
# ═══════════════════════════════════════════
import subprocess
import tempfile
import os


async def execute_python_code(code, timeout=30):
    """تنفيذ كود Python"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        result = subprocess.run(
            ['python', temp_path],
            capture_output=True, text=True, timeout=timeout,
            cwd=tempfile.gettempdir()
        )

        os.unlink(temp_path)

        if result.returncode == 0:
            return {'success': True, 'output': result.stdout[:3000] or "✅ تم بنجاح", 'error': None}
        else:
            return {'success': False, 'output': result.stdout[:1000], 'error': result.stderr[:2000]}

    except subprocess.TimeoutExpired:
        return {'success': False, 'output': None, 'error': f"⏰ انتهى الوقت ({timeout} ثانية)"}
    except Exception as e:
        return {'success': False, 'output': None, 'error': str(e)}


async def format_code_result(result):
    """تنسيق النتيجة"""
    if result['success']:
        return f"💻 النتيجة:\n```\n{result['output']}\n```"
    else:
        msg = f"❌ خطأ:\n```\n{result['error']}\n```"
        if result['output']:
            msg += f"\n📤 مخرجات:\n```\n{result['output']}\n```"
        return msg