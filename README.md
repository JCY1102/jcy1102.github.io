# 개인 연구 홈페이지 (Chanyoung Jeong)

ORCID 공개 기록과 DOI 메타데이터로 영문 한 페이지짜리 홈페이지와 CV PDF를 만든다. 배포 대상은 GitHub Pages(`jcy1102.github.io`)다.

## 구조

| 경로 | 내용 | 수정 주체 |
| --- | --- | --- |
| `config/profile.yaml` | 이름, 소속, 연구 소개, 연구 주제, 링크, ORCID 항목의 표기 | 직접 수정 |
| `config/journals.yaml` | 학술지별 SCIE/KCI 분류 | 새 학술지가 생기면 추가 |
| `data/orcid_cache.json` | ORCID·DOI 조회 결과. 조회 실패 시 이전 값을 유지한다 | `scripts/fetch_orcid.py` |
| `static/assets/` | 프로필 사진(720px), 배너(2400×1000), 파비콘 | 직접 교체 |
| `templates/` | 홈페이지(`index.html.j2`)와 CV(`cv.html.j2`) 틀 | |
| `scripts/build.py` | `_site/`에 페이지를 만들고 Chrome으로 CV PDF를 인쇄한다 | |
| `.github/workflows/deploy.yml` | 매일 03:00(KST)과 push할 때 수집, 빌드, 배포를 실행한다 | |

## 로컬 실행

저장소 최상위에서 공용 인터프리터로 실행한다.

```bash
.venv/Scripts/python.exe -m unittest discover -s projects/personal-homepage/tests
.venv/Scripts/python.exe projects/personal-homepage/scripts/fetch_orcid.py
.venv/Scripts/python.exe projects/personal-homepage/scripts/build.py
```

결과는 `_site/index.html`과 `_site/assets/Chanyoung_Jeong_CV.pdf`에 생긴다. `_site/`는 빌드 산출물이므로 버전 관리하지 않는다.

## 자동 갱신 규칙

- ORCID에 논문을 추가하면 다음 날 사이트와 CV에 반영된다. 저자·권호·쪽수는 DOI 메타데이터를 따른다.
- 학술지가 `journals.yaml`에 없으면 해당 논문은 "Unclassified"로 표시된다. 빌드 로그와 Actions 요약에 경고가 남는다.
- ORCID에 학력·경력·자격 항목을 새로 추가했는데 `profile.yaml`의 `affiliation_text`에 표기가 없으면, ORCID 원문 그대로 표시되고 경고가 남는다.
- ORCID 조회에 실패하면 캐시를 유지하므로 사이트가 비지 않는다.
- CV PDF는 매 빌드마다 같은 데이터로 새로 인쇄된다. 다운로드 링크에 갱신 날짜(`?v=YYYY-MM-DD`)를 붙여 방문자가 이전 PDF를 캐시로 받지 않게 한다. PDF 생성이 실패하면 빌드가 실패하고, 이전에 배포된 사이트와 PDF가 그대로 유지된다.

## 배포

- 사이트: https://jcy1102.github.io
- 저장소: https://github.com/JCY1102/jcy1102.github.io
- Settings → Pages → Source는 "GitHub Actions"여야 한다. "Deploy from a branch"로 두면 README가 사이트를 덮어쓴다.
- 이 폴더는 상위 Research 저장소의 `.gitignore`에 들어 있다. 다른 PC에서는 이 위치에 위 저장소를 clone한다.

## 수정하는 방법

| 바꿀 것 | 방법 |
| --- | --- |
| 논문, 학력, 경력, 자격 | ORCID에서 수정한다. 다음 날 03:00(KST)에 자동 반영된다. |
| 연구 소개, 연구 주제, 링크, 직함 표기 | `config/profile.yaml`을 고친 뒤 commit·push한다. |
| 새 학술지의 SCIE/KCI 분류 | `config/journals.yaml`에 추가한 뒤 commit·push한다. |
| 사진 | `static/assets/profile.jpg`(정사각형)나 `banner.jpg`(가로 2400×1000 권장)를 같은 이름으로 바꾸고 commit·push한다. |
| 디자인 | `templates/index.html.j2`(사이트), `templates/cv.html.j2`(CV)를 고친다. |
| 즉시 갱신 | 저장소 Actions 탭 → "Update from ORCID and deploy" → Run workflow. |

push 전에 로컬에서 `로컬 실행`의 세 명령으로 `_site/index.html`을 열어 확인할 수 있다. push하면 2~4분 뒤 사이트에 반영된다.

## 확인이 필요한 사항

- SCIE/KCI 분류는 학술지 이름으로 판단했다. 등재 목록(Clarivate MJL, KCI)과 대조하지 않았다.
- 자격증 영문 명칭은 Q-Net 공식 영문명과 대조하지 않았다.
- 공저자 영문 표기는 DOI 원자료를 그대로 쓴다. 같은 사람이 "Song J"와 "Song J-H"처럼 다르게 나올 수 있다.
