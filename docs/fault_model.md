# Fault 모델링 계약

이 프로젝트의 fault는 실제 부품 열화나 PCB 고장을 측정한 데이터가 아니라, 정상
SPICE netlist에 evaluator가 삽입하는 합성 benchmark 변형이다.

## Value fault

정상 R/L/C 부품값을 manifest에 기록된 값으로 교체한다. 초기 pilot은 0.5배,
0.7배, 1.3배, 2.0배 후보를 포함한다. evaluator는 정상 부품값을 exact binding한
후에만 교체하며, 값이 다르면 삽입을 거부한다.

## Open fault

대상 부품을 동일 두 노드 사이의 `1 TΩ` 저항으로 치환한다. 이는 수치적으로 유한한
SPICE 근사이며 실제 open 회로의 모든 누설·기생 효과를 표현하지 않는다.

## Short fault

대상 부품을 동일 두 노드 사이의 `1 mΩ` 저항으로 치환한다. 이는 수치적으로 유한한
SPICE 근사이며 실제 short의 배선 인덕턴스·접촉저항·기생 효과를 표현하지 않는다.

## Source/load impedance mismatch

ngspice RF port의 기준 임피던스 `z0`를 정상값 50 Ω에서 fault 값으로 변경한다.
이는 benchmark에서 정의한 port mismatch이며 실제 케이블, connector 또는 부하의
분포정수 효과까지 모델링하지 않는다.

## 유효 fault case 조건

fault 후보는 다음을 모두 만족할 때만 평가 case로 사용할 수 있다.

1. 정상 회로가 모든 specification을 통과한다.
2. fault 삽입이 exact healthy-value binding을 통과한다.
3. fault 회로가 ngspice에서 정상적으로 수렴한다.
4. fault 회로가 하나 이상의 필수 specification을 위반한다.
5. fault manifest는 Agent에게 제공되지 않는다.

현재 `faults/pilot/`의 사례는 최종 benchmark로 동결되지 않은 후보이다.

