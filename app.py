import json, os, random, unicodedata, base64
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response, jsonify
from werkzeug.utils import secure_filename
import eng_to_ipa as ipa_converter
from gtts import gTTS
from spellchecker import SpellChecker
import requests
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Thay đổi secret key cho phù hợp

# Cấu hình thư mục upload (ảnh và audio)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['AUDIO_UPLOAD_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'audio')
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['AUDIO_UPLOAD_FOLDER']):
    os.makedirs(app.config['AUDIO_UPLOAD_FOLDER'])

DATA_FILE = 'flashcards.json'

def load_data():
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        return data.get("big_decks", {}) if data else {}
    else:
        return {}

def save_data(big_decks):
    data = {"big_decks": big_decks}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def remove_diacritics(text):
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')

def check_answer(user_answer, correct_answers):
    user = remove_diacritics(user_answer.strip().lower())
    for ans in correct_answers:
        if user == remove_diacritics(ans.strip().lower()):
            return True
    return False

def generate_tts(word):
    filename = secure_filename(word) + ".mp3"
    filepath = os.path.join(app.config['AUDIO_UPLOAD_FOLDER'], filename)
    try:
        tts = gTTS(word, lang='en')
        tts.save(filepath)
        return url_for('static', filename='uploads/audio/' + filename) + f"?v={random.randint(1,100000)}"
    except Exception as e:
        return ""

def save_audio_blob(word, blob_data):
    try:
        header, encoded = blob_data.split(',', 1)
        data = base64.b64decode(encoded)
        filename = secure_filename(word) + "_direct.mp3"
        filepath = os.path.join(app.config['AUDIO_UPLOAD_FOLDER'], filename)
        with open(filepath, 'wb') as f:
            f.write(data)
        return url_for('static', filename='uploads/audio/' + filename) + f"?v={random.randint(1,100000)}"
    except Exception as e:
        return ""

# Endpoint tự sinh hình ảnh: sử dụng Unsplash để lấy hình, convert sang Base64
@app.route('/generate_image')
def generate_image():
    word = request.args.get('word', '').strip()
    if not word:
        return jsonify({"error": "No word provided"}), 400
    url = f"https://source.unsplash.com/featured/?{word}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            b64_str = base64.b64encode(response.content).decode('utf-8')
            data_uri = "data:image/jpeg;base64," + b64_str
            return jsonify({"image": data_uri})
        else:
            return jsonify({"error": "Failed to fetch image"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint kiểm tra từ
spell = SpellChecker(language='en')
@app.route('/check_word')
def check_word():
    word = request.args.get('word', '').strip()
    if not word:
        return jsonify({"error": "No word provided"}), 400
    if word.lower() in spell:
        correct = True
        suggestion = ""
    else:
        correct = False
        suggestion = spell.correction(word)
    ipa_text = ipa_converter.convert(word).replace("*", "")
    audio_url = generate_tts(word)
    return jsonify({
        "correct": correct,
        "suggestion": suggestion,
        "ipa": ipa_text,
        "audio": audio_url
    })

# Endpoint lấy danh sách khóa nhỏ của 1 khóa lớn
@app.route('/get_subdecks')
def get_subdecks():
    big_deck = request.args.get('big_deck', '').strip()
    data = load_data()
    subdecks_info = []
    if big_deck in data:
        for subdeck_name, subdeck_data in data[big_deck].get("subdecks", {}).items():
            # Tính số từ trong khóa nhỏ dựa vào số thẻ (mảng cards)
            card_count = len(subdeck_data.get("cards", []))
            subdecks_info.append({"name": subdeck_name, "count": card_count})
    return jsonify({"subdecks": subdecks_info})


# ------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/list')
def list_courses():
    decks = load_data()
    return render_template('list.html', decks=decks)

@app.route('/course/<big_deck>/<sub_deck>')
def course_detail(big_deck, sub_deck):
    data = load_data()
    if big_deck not in data or sub_deck not in data[big_deck]["subdecks"]:
        flash("Khóa học không tồn tại", "danger")
        return redirect(url_for('list_courses'))
    cards = data[big_deck]["subdecks"][sub_deck]["cards"]
    return render_template('course_detail.html', big_deck=big_deck, sub_deck=sub_deck, cards=cards)

@app.route('/create', methods=['GET', 'POST'])
def create():
    data = load_data()
    if request.method == 'POST':
        existing_big = request.form.get('existing_big_deck', '').strip()
        new_big = request.form.get('new_big_deck', '').strip()
        if existing_big:
            big_deck = existing_big
        elif new_big:
            big_deck = new_big
        else:
            flash("Vui lòng chọn hoặc nhập tên khóa lớn.", "danger")
            return redirect(url_for('create'))
        existing_sub = request.form.get('existing_sub_deck', '').strip()
        new_sub = request.form.get('new_sub_deck', '').strip()
        if existing_sub:
            sub_deck = existing_sub
        elif new_sub:
            sub_deck = new_sub
        else:
            flash("Vui lòng chọn hoặc nhập tên khóa nhỏ.", "danger")
            return redirect(url_for('create'))
        
        english = request.form.get('english', '').strip()
        description = request.form.get('description', '').strip()
        definitions_raw = request.form.get('definitions', '').strip()
        definitions = [line.strip() for line in definitions_raw.splitlines() if line.strip()]
        ipa_text = request.form.get('ipa', '').strip()
        if not ipa_text:
            ipa_text = ipa_converter.convert(english).replace("*", "")
        
        image_url = ""
        if 'image_file' in request.files:
            image_file = request.files['image_file']
            if image_file and image_file.filename != "":
                filename = secure_filename(image_file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(filepath)
                image_url = url_for('static', filename='uploads/' + filename)
        image_url = image_url or request.form.get('image', '').strip()
        
        audio_blob = request.form.get('audio_blob', '').strip()
        if audio_blob:
            audio_user_url = save_audio_blob(english, audio_blob)
        else:
            audio_user_url = ""
            if 'audio_file' in request.files:
                audio_file = request.files['audio_file']
                if audio_file and audio_file.filename != "":
                    filename = secure_filename(audio_file.filename)
                    filepath = os.path.join(app.config['AUDIO_UPLOAD_FOLDER'], filename)
                    audio_file.save(filepath)
                    audio_user_url = url_for('static', filename='uploads/audio/' + filename)
        audio_auto_url = generate_tts(english)
        
        if big_deck not in data:
            data[big_deck] = {"subdecks": {}}
        if sub_deck not in data[big_deck]["subdecks"]:
            data[big_deck]["subdecks"][sub_deck] = {"cards": []}
                
        card = {
            "english": english,
            "description": description,
            "definitions": definitions,
            "ipa": ipa_text,
            "image": image_url,
            "audio_auto": audio_auto_url,
            "audio_user": audio_user_url,
            "mistake_count": 0
        }

        data[big_deck]["subdecks"][sub_deck]["cards"].append(card)
        save_data(data)
        flash("Flashcard đã được tạo thành công!", "success")
        return redirect(url_for('create',
                        existing_big_deck=existing_big,
                        new_big_deck=new_big,
                        existing_sub_deck=existing_sub,
                        new_sub_deck=new_sub))

    return render_template('create.html', big_decks=load_data())

@app.route('/flashcard/add/<big_deck>/<sub_deck>', methods=['GET', 'POST'])
def add_flashcard(big_deck, sub_deck):
    data = load_data()
    if request.method == 'POST':
        english = request.form.get('english', '').strip()
        description = request.form.get('description', '').strip()
        definitions_raw = request.form.get('definitions', '').strip()
        definitions = [line.strip() for line in definitions_raw.splitlines() if line.strip()]
        ipa_text = request.form.get('ipa', '').strip()
        if not ipa_text:
            ipa_text = ipa_converter.convert(english).replace("*", "")
        image_url = ""
        if 'image_file' in request.files:
            image_file = request.files['image_file']
            if image_file and image_file.filename != "":
                filename = secure_filename(image_file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(filepath)
                image_url = url_for('static', filename='uploads/' + filename)
        image_url = image_url or request.form.get('image', '').strip()
        audio_blob = request.form.get('audio_blob', '').strip()
        if audio_blob:
            audio_user_url = save_audio_blob(english, audio_blob)
        else:
            audio_user_url = ""
            if 'audio_file' in request.files:
                audio_file = request.files['audio_file']
                if audio_file and audio_file.filename != "":
                    filename = secure_filename(audio_file.filename)
                    filepath = os.path.join(app.config['AUDIO_UPLOAD_FOLDER'], filename)
                    audio_file.save(filepath)
                    audio_user_url = url_for('static', filename='uploads/audio/' + filename)
        audio_auto_url = generate_tts(english)
        new_card = {
            "english": english,
            "description": description,
            "definitions": definitions,
            "ipa": ipa_text,
            "image": image_url,
            "audio_auto": audio_auto_url,
            "audio_user": audio_user_url,
            "mistake_count": 0
        }

        if big_deck not in data or sub_deck not in data[big_deck]["subdecks"]:
            flash("Khóa học không tồn tại", "danger")
            return redirect(url_for('list_courses'))
        data[big_deck]["subdecks"][sub_deck]["cards"].append(new_card)
        save_data(data)
        flash("Flashcard mới đã được thêm!", "success")
        return redirect(url_for('course_detail', big_deck=big_deck, sub_deck=sub_deck))
    return render_template('flashcard_form.html', action="Add", big_deck=big_deck, sub_deck=sub_deck, card=None)

@app.route('/flashcard/edit/<big_deck>/<sub_deck>/<int:card_index>', methods=['GET', 'POST'])
def edit_flashcard(big_deck, sub_deck, card_index):
    data = load_data()
    try:
        card = data[big_deck]["subdecks"][sub_deck]["cards"][card_index]
    except (KeyError, IndexError):
        flash("Flashcard không tồn tại", "danger")
        return redirect(url_for('course_detail', big_deck=big_deck, sub_deck=sub_deck))
    if request.method == 'POST':
        english = request.form.get('english', '').strip()
        description = request.form.get('description', '').strip()
        definitions_raw = request.form.get('definitions', '').strip()
        definitions = [line.strip() for line in definitions_raw.splitlines() if line.strip()]
        ipa_text = request.form.get('ipa', '').strip()
        if not ipa_text:
            ipa_text = ipa_converter.convert(english).replace("*", "")
        image_url = ""
        if 'image_file' in request.files:
            image_file = request.files['image_file']
            if image_file and image_file.filename != "":
                filename = secure_filename(image_file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(filepath)
                image_url = url_for('static', filename='uploads/' + filename)
        image_url = image_url or request.form.get('image', '').strip()
        audio_blob = request.form.get('audio_blob', '').strip()
        if audio_blob:
            audio_user_url = save_audio_blob(english, audio_blob)
        else:
            audio_user_url = ""
            if 'audio_file' in request.files:
                audio_file = request.files['audio_file']
                if audio_file and audio_file.filename != "":
                    filename = secure_filename(audio_file.filename)
                    filepath = os.path.join(app.config['AUDIO_UPLOAD_FOLDER'], filename)
                    audio_file.save(filepath)
                    audio_user_url = url_for('static', filename='uploads/audio/' + filename)
        audio_auto_url = generate_tts(english)
        card.update({
            "english": english,
            "description": description,
            "definitions": definitions,
            "ipa": ipa_text,
            "image": image_url,
            "audio_auto": audio_auto_url,
            "audio_user": audio_user_url,
            "mistake_count": card.get("mistake_count", 0)
        })
        save_data(data)
        flash("Flashcard đã được cập nhật!", "success")
        return redirect(url_for('course_detail', big_deck=big_deck, sub_deck=sub_deck))
    return render_template('flashcard_form.html', action="Edit", big_deck=big_deck, sub_deck=sub_deck, card=card)

@app.route('/flashcard/delete/<big_deck>/<sub_deck>/<int:card_index>', methods=['POST'])
def delete_flashcard(big_deck, sub_deck, card_index):
    data = load_data()
    try:
        del data[big_deck]["subdecks"][sub_deck]["cards"][card_index]
        save_data(data)
        flash("Flashcard đã được xóa.", "success")
    except (KeyError, IndexError):
        flash("Không thể xóa flashcard.", "danger")
    return redirect(url_for('course_detail', big_deck=big_deck, sub_deck=sub_deck))

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        topic = request.form.get('topic', '').strip()
        description = request.form.get('description', '').strip()
        try:
            count = int(request.form.get('count', '5'))
        except:
            count = 5
        generated = []
        topic_lower = topic.lower()
        if "tay" in topic_lower:
            vocabulary = ["cầm", "nắm", "vẫy tay", "tát", "ôm"]
            for word in vocabulary:
                definitions = [f"Định nghĩa cho {word}"]
                ipa_text = ipa_converter.convert(word).replace("*", "")
                image_url = f"https://source.unsplash.com/featured/?{word}"
                audio_auto_url = generate_tts(word)
                generated.append({
                    "english": word,
                    "description": f"Mô tả cho {word}",
                    "definitions": definitions,
                    "ipa": ipa_text,
                    "image": image_url,
                    "audio_auto": audio_auto_url,
                    "audio_user": ""
                })
        else:
            for i in range(count):
                word = f"{topic} {i+1}"
                definitions = [f"Định nghĩa cho {word}"]
                ipa_text = ipa_converter.convert(word).replace("*", "")
                image_url = f"https://source.unsplash.com/featured/?{topic}"
                audio_auto_url = generate_tts(word)
                generated.append({
                    "english": word,
                    "description": f"Mô tả cho {word}",
                    "definitions": definitions,
                    "ipa": ipa_text,
                    "image": image_url,
                    "audio_auto": audio_auto_url,
                    "audio_user": ""
                })
        session['generated'] = generated
        return redirect(url_for('generate_result'))
    return render_template('generate.html')

@app.route('/generate/result', methods=['GET', 'POST'])
def generate_result():
    generated = session.get('generated', [])
    if request.method == 'POST':
        selected_indices = request.form.getlist('selected')
        target_big = request.form.get('big_deck').strip()
        target_sub = request.form.get('sub_deck').strip()
        data = load_data()
        if target_big not in data:
            data[target_big] = {"subdecks": {}}
        if target_sub not in data[target_big]["subdecks"]:
            data[target_big]["subdecks"][target_sub] = {"cards": []}
        for idx in selected_indices:
            idx = int(idx)
            data[target_big]["subdecks"][target_sub]["cards"].append(generated[idx])
        save_data(data)
        flash("Các flashcard đã được thêm thành công!", "success")
        session.pop('generated', None)
        return redirect(url_for('list_courses'))
    return render_template('generate_result.html', generated=generated)

@app.route('/get_words')
def get_words():
    big_deck = request.args.get('big_deck')
    sub_decks = request.args.getlist('sub_deck')
    data = load_data()
    grouped_words = {}  # key: sub_deck, value: list các từ (english)
    if big_deck == "all":
        for bd, bd_data in data.items():
            for sd, sd_data in bd_data.get("subdecks", {}).items():
                for card in sd_data.get("cards", []):
                    word = card.get("english", "")
                    if word:
                        if sd not in grouped_words:
                            grouped_words[sd] = []
                        if word not in grouped_words[sd]:
                            grouped_words[sd].append(word)
    else:
        for sub in sub_decks:
            for card in data.get(big_deck, {}).get("subdecks", {}).get(sub, {}).get("cards", []):
                word = card.get("english", "")
                if word:
                    if sub not in grouped_words:
                        grouped_words[sub] = []
                    if word not in grouped_words[sub]:
                        grouped_words[sub].append(word)
    return jsonify({"grouped_words": grouped_words})


@app.route('/test/select', methods=['GET', 'POST'])
def test_select():
    data = load_data()
    decks = [{"big_deck": big, "subdecks": list(bd_data.get("subdecks", {}).keys())} 
             for big, bd_data in data.items()]

    if request.method == 'POST':
        selected_big = request.form.get('big_deck')
        selected_subs = request.form.getlist('sub_deck')  # Danh sách các khóa nhỏ được chọn
        order_mode = request.form.get('order_mode', 'sequential')  # 'sequential' hoặc 'random'
        only_english = 'only_english' in request.form  # Kiểm tra checkbox có được chọn không
        
        # Tạo danh sách flashcard
        flashcards = []
        if selected_big == "all":
            for bd, bd_data in data.items():
                for sd, sd_data in bd_data.get("subdecks", {}).items():
                    for card in sd_data.get("cards", []):
                        flashcards.append({
                            "big_deck": bd,
                            "sub_deck": sd,
                            "card": card
                        })
        else:
            for sub in selected_subs:
                for card in data[selected_big]["subdecks"].get(sub, {}).get("cards", []):
                    flashcards.append({
                        "big_deck": selected_big,
                        "sub_deck": sub,
                        "card": card
                    })

        # Lọc theo các từ được chọn (dựa trên trường "english")
        selected_words = request.form.getlist('selected_word')
        if selected_words:
            flashcards = [fc for fc in flashcards if fc["card"].get("english") in selected_words]

        if not flashcards:
            flash("Không tìm thấy flashcard.", "danger")
            return redirect(url_for('test_select'))
        
        # Xác định số câu hỏi: gấp đôi tổng số từ
        total_cards = len(flashcards)
        num_questions = total_cards * 2

        questions_flashcards = []
        # Phần đầu tiên: lấy toàn bộ flashcard theo thứ tự ban đầu
        questions_flashcards.extend(flashcards)
        
        # Phần bổ sung: chọn ngẫu nhiên từ danh sách có sẵn
        additional_count = num_questions - total_cards
        for _ in range(additional_count):
            questions_flashcards.append(random.choice(flashcards))
        
        # Tạo danh sách câu hỏi với các trường cần thiết
        questions = []
        for fc in questions_flashcards:
            question = {
                "big_deck": fc["big_deck"],
                "sub_deck": fc["sub_deck"],
                "card": fc["card"],
                "attempt": 0
            }
            if only_english:
                question["mode"] = "only_english"  # Chỉ nhập tiếng Anh, hiển thị Tiếng Việt
            else:
                question["mode"] = random.choice([1, 2])  # Chọn ngẫu nhiên 1 hoặc 2
            questions.append(question)

        session['test'] = {"questions": questions, "current": 0, "score": 0, "total": num_questions}
        return redirect(url_for('test'))
    
    return render_template('test_select.html', decks=decks)





@app.route('/test', methods=['GET', 'POST'])
def test():
    test_data = session.get('test')
    if not test_data:
        return redirect(url_for('test_select'))
    current_index = test_data['current']
    questions = test_data['questions']
    score = test_data['score']
    total = test_data['total']
    if current_index >= total:
        final_score = score
        session.pop('test')
        return render_template('test_result.html', score=final_score, total=total)
    
    current_question = questions[current_index]
    card = current_question['card']
    mode = current_question['mode']
    show_audio = True if mode == 1 else False  # Chỉ hiển thị IPA và audio nếu mode 1

    if mode == 1:
        question_text = f"Nhập định nghĩa cho từ: <strong>{card['english']}</strong> (IPA: {card.get('ipa','')})"
        correct_answers = card['definitions']
    else:
        definition = random.choice(card['definitions'])
        question_text = f"Nhập từ tiếng Anh cho định nghĩa: <strong>{definition}</strong>"
        correct_answers = [card['english']]
    
    hint = ""
    if request.method == 'POST':
        user_answer = request.form.get('answer', '')
        if check_answer(user_answer, correct_answers):
            flash("Chính xác!", "success")
            test_data['score'] += 1
            test_data['current'] += 1
            session['test'] = test_data
            return redirect(url_for('test'))
        else:
            if current_question['attempt'] == 0:
                current_question['attempt'] += 1
                correct = correct_answers[0]
                hint = correct[:2] + "*" * (len(correct) - 2)
                flash("Sai! Hãy nhập lại. Gợi ý hiển thị bên dưới.", "warning")
                session['test'] = test_data
                # Cập nhật mistake_count cho flashcard trong dữ liệu lưu trữ
                data = load_data()
                bd = current_question["big_deck"]
                sd = current_question["sub_deck"]
                card_obj = current_question["card"]
                for i, c in enumerate(data[bd]["subdecks"][sd]["cards"]):
                    if c["english"] == card_obj["english"] and c.get("description", "") == card_obj.get("description", ""):
                        data[bd]["subdecks"][sd]["cards"][i]["mistake_count"] = c.get("mistake_count", 0) + 1
                        break
                save_data(data)
            else:
                flash(f"Sai! Đáp án đúng: {correct_answers[0]}", "danger")
                test_data['current'] += 1
                session['test'] = test_data
                return redirect(url_for('test'))

    # Luôn trả về một response hợp lệ (GET request hoặc sau xử lý POST không chuyển hướng)
    return render_template('test.html',
                           question=question_text,
                           hint=hint,
                           current=current_index+1,
                           total=total,
                           card=card,
                           show_audio=show_audio)

@app.route('/reset')
def reset():
    session.pop('test', None)
    return redirect(url_for('test_select'))

# --- Route: Lựa chọn luyện tập ---
@app.route('/practice/select', methods=['GET', 'POST'])
def practice_select():
    data = load_data()
    # Tạo danh sách decks: mỗi phần tử là dict với key "big_deck" và "subdecks"
    decks = []
    for big_deck, bd_data in data.items():
        subdecks = list(bd_data.get("subdecks", {}).keys())
        decks.append({"big_deck": big_deck, "subdecks": subdecks})

    if request.method == 'POST':
        # Lấy dữ liệu từ form
        selected_big = request.form.get('big_deck')
        selected_sub = request.form.get('sub_deck')
        try:
            num_questions = int(request.form.get('num_questions'))
        except:
            num_questions = 5

        flashcards = []
        # Nếu người dùng chọn "all" cho khóa lớn, lấy tất cả flashcard của mọi khóa
        if selected_big == "all":
            for bd, bd_data in data.items():
                for sd, sd_data in bd_data.get("subdecks", {}).items():
                    for card in sd_data.get("cards", []):
                        flashcards.append({
                            "big_deck": bd,
                            "sub_deck": sd,
                            "card": card
                        })
        else:
            bd_data = data.get(selected_big, {})
            # Nếu người dùng chọn "all" cho khóa nhỏ, lấy tất cả flashcard của khóa lớn đó
            if selected_sub == "all":
                for sd, sd_data in bd_data.get("subdecks", {}).items():
                    for card in sd_data.get("cards", []):
                        flashcards.append({
                            "big_deck": selected_big,
                            "sub_deck": sd,
                            "card": card
                        })
            else:
                # Nếu đã chọn cụ thể một khóa nhỏ
                for card in bd_data.get("subdecks", {}).get(selected_sub, {}).get("cards", []):
                    flashcards.append({
                        "big_deck": selected_big,
                        "sub_deck": selected_sub,
                        "card": card
                    })

        if not flashcards:
            flash("Không tìm thấy flashcard cho bộ đã chọn.", "danger")
            return redirect(url_for('practice_select'))

        # Gán id duy nhất cho mỗi flashcard để theo dõi số lần sử dụng
        for idx, item in enumerate(flashcards):
            item['id'] = idx

        questions = []
        card_usage = {}  # theo dõi số lần flashcard đã được dùng (dựa trên id)

        # Lựa chọn ngẫu nhiên flashcard dựa trên mistake_count (nếu không có, mặc định là 0)
        while len(questions) < num_questions:
            eligible = [item for item in flashcards if card_usage.get(item['id'], 0) < 2]
            if not eligible:
                break  # Không còn flashcard đủ điều kiện
            weights = [item['card'].get('mistake_count', 0) + 1 for item in eligible]
            chosen = random.choices(eligible, weights=weights, k=1)[0]
            card_usage[chosen['id']] = card_usage.get(chosen['id'], 0) + 1
            mode = random.choice([1, 2])
            questions.append({
                "big_deck": chosen["big_deck"],
                "sub_deck": chosen["sub_deck"],
                "card": chosen["card"],
                "mode": mode,
                "attempt": 0
            })

        # Lưu phiên luyện tập vào session với key "practice"
        session['practice'] = {"questions": questions, "current": 0, "score": 0, "total": len(questions)}
        return redirect(url_for('practice'))

    # Với GET, render template practice_select.html và truyền danh sách decks
    return render_template('practice_select.html', decks=decks)


# --- Route: Luyện tập (hiển thị một flashcard) ---
# --- Route: Luyện tập (hiển thị một flashcard) ---
@app.route('/practice', methods=['GET', 'POST'])
def practice():
    practice_session = session.get('practice')
    if not practice_session or practice_session.get('total', 0) == 0:
        flash("Không có flashcard luyện tập.", "danger")
        return redirect(url_for('practice_select'))

    # Đảm bảo sử dụng đúng key
    cards = practice_session["questions"]
    current_index = practice_session["current"]

    # Nếu đã luyện tập hết
    if current_index >= len(cards):
        flash("Luyện tập hoàn thành!", "success")
        session.pop('practice')
        return redirect(url_for('list_courses'))

    current_item = cards[current_index]
    card = current_item["card"]
    mode = current_item["mode"]

    # Xác định nội dung hiển thị dựa trên mode
    if mode == 1:
        # Mode 1: Hiển thị từ tiếng Anh, đáp án là định nghĩa
        front_content = card.get("english", "")
        answer = card.get("definitions", [""])[0]
        additional = {
            "ipa": card.get("ipa", ""),
            "audio": card.get("audio_auto", ""),
            "audio_user": card.get("audio_user", ""),
            "image": card.get("image", ""),
            "english": card.get("english", ""),
            "definitions": card.get("definitions", [""])[0]
        }
    else:
        # Mode 2: Hiển thị định nghĩa, đáp án là từ tiếng Anh
        front_content = card.get("definitions", [""])[0]
        answer = card.get("english", "")
        additional = {
            "ipa": card.get("ipa", ""),
            "audio": card.get("audio_auto", ""),
            "image": card.get("image", ""),
            "audio_user": card.get("audio_user", ""),
            "english": card.get("english", ""),
            "definitions": card.get("definitions", [""])[0]
        }

    if request.method == "POST":
        user_answer = request.form.get("answer", "").strip()
        if check_answer(user_answer, [answer]):
            flash("Chính xác!", "success")
        else:
            flash(f"Sai! Đáp án đúng: {answer}", "danger")

        # Sau khi trả lời, chuyển sang card kế tiếp
        practice_session["current"] = current_index + 1
        session['practice'] = practice_session
        return redirect(url_for('practice'))

    return render_template('practice.html',
                           front=front_content,
                           additional=additional,
                           mode=mode,
                           current=current_index + 1,
                           total=len(cards))

# --- Route: Điều hướng qua card trước/sau (nếu muốn cho phép quay lại) ---
@app.route('/practice/navigate/<direction>')
def practice_navigate(direction):
    practice_session = session.get('practice')
    if not practice_session:
        return redirect(url_for('practice_select'))

    # Lấy chỉ số hiện tại từ key "current"
    current = practice_session.get("current", 0)
    questions = practice_session.get("questions", [])
    if not questions:
        return redirect(url_for('practice_select'))

    if direction == "next":
        practice_session["current"] = min(current + 1, len(questions) - 1)
    elif direction == "prev":
        practice_session["current"] = max(current - 1, 0)
    else:
        flash("Hướng điều hướng không hợp lệ.", "danger")
        return redirect(url_for('practice'))

    session['practice'] = practice_session
    return redirect(url_for('practice'))

DATA_FILE = os.path.join(os.path.dirname(__file__), 'flashcards.json')

EXPORT_FILE = r"E:\flashcard_web\flashcards.json"

@app.route('/export_data')
def export_data():
    try:
        # Đọc dữ liệu từ file JSON gốc
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Chuyển đổi dữ liệu thành chuỗi JSON với định dạng đẹp (indent=4)
    json_str = json.dumps(data, ensure_ascii=False, indent=4)

    try:
        # Ghi chuỗi JSON vào file tại đường dẫn EXPORT_FILE
        with open(EXPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(json_str)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Trả về thông báo thành công (bạn có thể tùy chỉnh giao diện response)
    return jsonify({
        "status": "success",
        "message": f"Data exported successfully to {EXPORT_FILE}"
    })



if __name__ == '__main__':
    app.run(debug=True)
