# SDK 설치 확인

실행일: 2026-09-24

## Aardvark

`aardvark-py` 설치 자체는 가능했지만, 현재 DevSpace Max의 Apple Silicon Python에서 import가 실패했다.

- Python: 3.14.7
- 설치된 PyPI wheel: `aardvark_py 5.30.2`
- 실패 원인: wheel에 포함된 macOS shared library가 `x86_64`, 실행 환경은 `arm64`
- 실제 장치 probe까지 도달하지 못함
- 임시 venv는 제거했으며 저장소에는 의존성을 추가하지 않음

Total Phase 공식 Aardvark Software API v6.00 페이지에는 Mac ARM 64-bit 패키지가 별도로 제공된다. 따라서 다음 실제 설치 경로는 공식 v6.00 Mac ARM package이며, USB Aardvark 장치 연결 후에만 device enumeration과 transaction smoke test를 수행한다.

공식 자료: [Aardvark Software API downloads](https://www.totalphase.com/products/aardvark-software-api/), [Total Phase downloads](https://www.totalphase.com/downloads/)

## TRACE32

`t32rem`과 Python Remote API는 Lauterbach TRACE32 설치 디렉터리와 라이선스에 포함되는 vendor 배포물이다. 현재 Max에는 실행 파일과 module이 없으므로 자동 설치하지 않았다. `t32rem`은 PowerView가 실행 중이고 Remote API가 활성화된 환경에서만 의미가 있다.

공식 자료: [t32rem usage](https://support.lauterbach.com/kb/articles/how-to-use-the-t32rem-tool), [Remote API](https://www2.lauterbach.com/pdf/api_remote_c.pdf)

## 현재 결론

- 설치 가능한 순수 소프트웨어: client wrapper, fixture, fake SDK, contract test
- 공식 vendor package가 필요한 것: Aardvark Mac ARM API, TRACE32/t32rem
- 물리 장비가 필요한 것: Aardvark device enumeration, 실제 I²C/SPI transaction, TRACE32 target/JTAG 접근
