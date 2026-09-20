# UefiCpuPkg (UEFI CPU Package) 상세 분석 보고서

## 1. 패키지 개요 (Overview)

- **패키지 디렉터리**: `UefiCpuPkg/`
- **분류 (Category)**: Hardware & Architecture
- **주요 실행 단계 (Target Phases)**: `SEC, PEI, DXE, SMM`
- **포함된 모듈 수**: 총 75개 (`.inf` 모듈 기준)

x86, x64 및 RISC-V 프로세서의 초기화, 멀티프로세서(MP) 서비스, SMM(System Management Mode) 인프라, CPU Reset Vector 및 캐시(MTRR) 제어를 전담하는 하드웨어 저수준 패키지입니다.

---

## 2. 패키지 아키텍처 및 시스템 블록 다이어그램

```mermaid
flowchart TD
    subgraph UefiCpuPkg_Architecture["UefiCpuPkg 실행 구조"]
        subgraph ResetAndSec["1. 전원 인가 및 초기화 (ResetVector & SecCore)"]
            RESET_VEC["ResetVector<br>(16비트 리셋 벡터 0xFFFFFFF0 점프, 32비트 보호모드 전환)"]
            SEC_CORE["SecCore<br>(CAR: Cache-as-RAM MTRR 활성화, 임시 스택 설정)"]
        end

        subgraph PEI_MP["2. PEI 단계 멀티코어 제어 (CpuMpPei)"]
            MP_PEI["CpuMpPei<br>(EFI_PEI_MP_SERVICES_PPI 등록)"]
            LOCAL_APIC["LocalApicLib<br>(APIC ID, Timer, IPI 신호 전송)"]
        end

        subgraph DXE_CPU["3. DXE CPU 관리 (CpuDxe)"]
            CPU_DXE["CpuDxe<br>(EFI_CPU_ARCH_PROTOCOL, 인터럽트 핸들러 IDT 구성)"]
            MTRR_LIB["MtrrLib<br>(메모리 캐시 속성 WB/WC/UC 매핑)"]
            MICROCODE["MicrocodeMeasurementDxe<br>(CPU 마이크로코드 패치 검증)"]
        end

        subgraph SMM_INFRA["4. SMM 보안 실행 환경 (PiSmmCpuDxeSmm)"]
            SMM_CPU["PiSmmCpuDxeSmm<br>(SMM 진입 벡터, SMI 핸들러 관리, Save State 영역 파싱)"]
            SMM_FEAT["CpuFeaturesLib<br>(VT-x, VMX, SMX, SGX, CET 보안 기능 설정)"]
        end
    end

    RESET_VEC --> SEC_CORE
    SEC_CORE --> MP_PEI
    MP_PEI --> CPU_DXE
    CPU_DXE --> SMM_INFRA
```

---

## 3. 핵심 아키텍처 및 심층 분석

### 핵심 모듈 및 서브디렉터리 분석
1. **`ResetVector/`**:
   - x86 CPU가 전원을 켰을 때 실행되는 최초의 명령(`0xFFFFFFF0`)이 위치합니다. 16비트 Real Mode에서 GDT를 로드하고 32비트 Flat Protected Mode 또는 64비트 Long Mode로 전환합니다.
2. **`SecCore/`**:
   - 물리 메모리(DRAM)가 없는 상태에서 CPU L2/L3 캐시를 임시 RAM으로 활용하는 **CAR (Cache-as-RAM)** 메커니즘을 구성하고, PEI Core 호출을 위한 스택을 준비합니다.
3. **`PiSmmCpuDxeSmm/`**:
   - SMM(System Management Mode)의 CPU 제어를 총괄합니다. SMI(System Management Interrupt) 발생 시 CPU 코어들이 SMM RAM(SMRAM)으로 점프하여 안전한 고신뢰 코드(UEFI 보안 변수 보호, 전원 관리)를 실행할 수 있도록 환경을 조성합니다.

---

## 4. 핵심 실행 워크플로우 및 시퀀스 다이어그램

```mermaid
sequenceDiagram
    autonumber
    participant BSP as Boot Strap Processor (BSP)
    participant AP as Application Processors (APs)
    participant Sec as SecCore (CAR)
    participant MpPei as CpuMpPei
    participant SmmCpu as PiSmmCpuDxeSmm

    BSP->>Sec: Reset Vector 실행 및 MTRR CAR 활성화
    Sec->>MpPei: PEI 진입 및 MP Services PPI 등록
    MpPei->>AP: INIT-SIPI-SIPI 시퀀스 전송 (IPI)
    AP-->>MpPei: AP 깨어남 및 대기 루프 진입
    MpPei->>SmmCpu: DXE/SMM 단계 진입
    Note over SmmCpu: SMM Base (SMBASE) 재배치 및 SMI 핸들러 설치
    Note over BSP,AP: 하드웨어 SMI 발생 시 모든 코어가 SMM 모드로 동시 진입
```

---

## 5. 제공 및 소비하는 주요 Protocols / PPIs / PCDs

### 5.1 주요 Protocols (DXE/SMM)
- `gEfiSmmCpuServiceProtocolGuid`
- `gEdkiiSmmCpuRendezvousProtocolGuid`
- `gEfiSmMonitorInitProtocolGuid`
- `gRiscVEfiBootProtocolGuid`

### 5.2 주요 PPIs (PEI)
- `gEdkiiPeiMpServices2PpiGuid`
- `gEdkiiPeiShadowMicrocodePpiGuid`
- `gRepublishSecPpiPpiGuid`

---

## 6. 주요 모듈 및 소스 파일 맵 (Module Summary Table)

| 모듈 유형 | 모듈명 (BASE_NAME) | 소스 경로 (.inf) |
|---|---|---|
| `BASE` | **AmdSvsmLibNull** | `Library/AmdSvsmLibNull/AmdSvsmLibNull.inf` |
| `BASE` | **ArmMmuBaseLib** | `Library/ArmMmuLib/ArmMmuBaseLib.inf` |
| `BASE` | **UefiCpuBaseArchSupportLib** | `Library/BaseArchSupportLib/BaseArchSupportLib.inf` |
| `BASE` | **BaseRiscVMmuLib** | `Library/BaseRiscVMmuLib/BaseRiscVMmuLib.inf` |
| `BASE` | **BaseXApicLib** | `Library/BaseXApicLib/BaseXApicLib.inf` |
| `BASE` | **BaseXApicX2ApicLib** | `Library/BaseXApicX2ApicLib/BaseXApicX2ApicLib.inf` |
| `DXE_DRIVER` | **CpuDxe** | `CpuDxe/CpuDxe.inf` |
| `DXE_DRIVER` | **CpuDxeRiscV64** | `CpuDxeRiscV64/CpuDxeRiscV64.inf` |
| `DXE_DRIVER` | **CpuFeaturesDxe** | `CpuFeatures/CpuFeaturesDxe.inf` |
| `DXE_DRIVER` | **CpuIo2Dxe** | `CpuIo2Dxe/CpuIo2Dxe.inf` |
| `DXE_DRIVER` | **CpuMmio2Dxe** | `CpuMmio2Dxe/CpuMmio2Dxe.inf` |
| `DXE_DRIVER` | **CpuS3DataDxe** | `CpuS3DataDxe/CpuS3DataDxe.inf` |
| `DXE_SMM_DRIVER` | **CpuIo2Smm** | `CpuIo2Smm/CpuIo2Smm.inf` |
| `DXE_SMM_DRIVER` | **AmdSysCallLibNull** | `Library/AmdSysCallLibNull/AmdSysCallLibNull.inf` |
| `DXE_SMM_DRIVER` | **SmmCpuExceptionHandlerLib** | `Library/CpuExceptionHandlerLib/SmmCpuExceptionHandlerLib.inf` |
| `DXE_SMM_DRIVER` | **AmdMmSaveStateLib** | `Library/MmSaveStateLib/AmdMmSaveStateLib.inf` |
| `DXE_SMM_DRIVER` | **IntelMmSaveStateLib** | `Library/MmSaveStateLib/IntelMmSaveStateLib.inf` |
| `DXE_SMM_DRIVER` | **AmdSmmCpuFeaturesLib** | `Library/SmmCpuFeaturesLib/AmdSmmCpuFeaturesLib.inf` |
| `HOST_APPLICATION` | **CpuPageTableLibUnitTestHost** | `Library/CpuPageTableLib/UnitTest/CpuPageTableLibUnitTestHost.inf` |
| `HOST_APPLICATION` | **MtrrLibUnitTestHost** | `Library/MtrrLib/UnitTest/MtrrLibUnitTestHost.inf` |
| `MM_STANDALONE` | **CpuIo2StandaloneMm** | `CpuIo2Smm/CpuIo2StandaloneMm.inf` |
| `MM_STANDALONE` | **AmdStandaloneMmCpuFeaturesLib** | `Library/SmmCpuFeaturesLib/AmdStandaloneMmCpuFeaturesLib.inf` |
| `MM_STANDALONE` | **StandaloneMmCpuFeaturesLib** | `Library/SmmCpuFeaturesLib/StandaloneMmCpuFeaturesLib.inf` |
| `MM_STANDALONE` | **PiSmmCpuStandaloneMm** | `PiSmmCpuDxeSmm/PiSmmCpuStandaloneMm.inf` |
| `PEIM` | **CpuFeaturesPei** | `CpuFeatures/CpuFeaturesPei.inf` |
| ... | *(총 75개 모듈 중 대표 모듈 25개 수록)* | ... |

---

## 7. 관련 문서 및 참조 링크

- [EDK II 전체 아키텍처 개요](../EDK2_Architecture_Overview.md)
- [전체 패키지 분석 인덱스](Package_Analysis_Index.md)
- [FatPkg 상세 분석 보고서](FatPkg_Analysis.md)