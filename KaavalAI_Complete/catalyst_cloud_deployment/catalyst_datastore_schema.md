# KaavalAI — Catalyst Data Store Schema Reference

Catalyst only allows table/column creation via the **console** (no programmatic DDL —
ZCQL handles queries, not schema). Create these in order (lookups first, so Foreign Key
columns can reference them). Column names below match the CSV headers exactly, so the
bulk-load script needs no renaming.

**Data types available in Catalyst:** `Var Char` (≤255 chars), `Text` (≤10,000 chars),
`Int` (4-byte), `BigInt` (8-byte), `Double`, `Boolean`, `DateTime`, `Foreign Key`.
There is no native `Date`-only type — use `DateTime` for date columns too.

## Tier 1 — Root lookups (no dependencies)
| Table | Columns (name: type) |
|---|---|
| `State` | StateID: Int (Is Unique) · StateName: Var Char(100) · NationalityID: Int · Active: Boolean |
| `UnitType` | UnitTypeID: Int (Is Unique) · UnitTypeName: Var Char(100) · CityDistState: Var Char(50) · Hierarchy: Int · Active: Boolean |
| `Rank` | RankID: Int (Is Unique) · RankName: Var Char(100) · Hierarchy: Int · Active: Boolean |
| `Designation` | DesignationID: Int (Is Unique) · DesignationName: Var Char(100) · Active: Boolean · SortOrder: Int |
| `CaseCategory` | CaseCategoryID: Int (Is Unique) · LookupValue: Var Char(50) |
| `GravityOffence` | GravityOffenceID: Int (Is Unique) · LookupValue: Var Char(50) |
| `CrimeHead` | CrimeHeadID: Int (Is Unique) · CrimeGroupName: Var Char(100) · Active: Boolean |
| `Act` | ActCode: Var Char(20) (Is Unique) · ActDescription: Var Char(255) · ShortName: Var Char(50) · Active: Boolean |
| `CaseStatusMaster` | CaseStatusID: Int (Is Unique) · CaseStatusName: Var Char(50) |
| `CasteMaster` | caste_master_id: Int (Is Unique) · caste_master_name: Var Char(100) |
| `ReligionMaster` | ReligionID: Int (Is Unique) · ReligionName: Var Char(50) |
| `OccupationMaster` | OccupationID: Int (Is Unique) · OccupationName: Var Char(100) |

## Tier 2 — Depends on Tier 1
| Table | Columns |
|---|---|
| `District` | DistrictID: Int (Is Unique) · DistrictName: Var Char(100) · StateID: Foreign Key → State · Active: Boolean |
| `Section` | ActCode: Foreign Key → Act · SectionCode: Var Char(20) · SectionDescription: Var Char(255) · Active: Boolean |
| `CrimeSubHead` | CrimeSubHeadID: Int (Is Unique) · CrimeHeadID: Foreign Key → CrimeHead · CrimeHeadName: Var Char(100) · SeqID: Int |
| `CrimeHeadActSection` | CrimeHeadID: Foreign Key → CrimeHead · ActCode: Foreign Key → Act · SectionCode: Var Char(20) |

## Tier 3 — Depends on Tier 2
| Table | Columns |
|---|---|
| `Court` | CourtID: Int (Is Unique) · CourtName: Var Char(150) · DistrictID: Foreign Key → District · StateID: Foreign Key → State · Active: Boolean |
| `Unit` | UnitID: Int (Is Unique) · UnitName: Var Char(150) · TypeID: Foreign Key → UnitType · ParentUnit: Int · NationalityID: Int · StateID: Foreign Key → State · DistrictID: Foreign Key → District · Active: Boolean · UnitCode4Digit: Var Char(10) |

## Tier 4 — Depends on Tier 3
| Table | Columns |
|---|---|
| `Employee` | EmployeeID: Int (Is Unique) · DistrictID: Foreign Key → District · UnitID: Foreign Key → Unit · RankID: Foreign Key → Rank · DesignationID: Foreign Key → Designation · KGID: Var Char(20) · FirstName: Var Char(100) · EmployeeDOB: DateTime · GenderID: Var Char(5) · BloodGroupID: Var Char(5) · PhysicallyChallenged: Boolean · AppointmentDate: DateTime |

## Tier 5 — CaseMaster (the FIR hub) and its children
| Table | Columns |
|---|---|
| `CaseMaster` | CaseMasterID: Int (Is Unique) · CrimeNo: Var Char(20) · CaseNo: Var Char(20) · CrimeRegisteredDate: DateTime · PolicePersonID: Foreign Key → Employee · PoliceStationID: Foreign Key → Unit · CaseCategoryID: Foreign Key → CaseCategory · GravityOffenceID: Foreign Key → GravityOffence · CrimeMajorHeadID: Foreign Key → CrimeHead · CrimeMinorHeadID: Foreign Key → CrimeSubHead · CaseStatusID: Foreign Key → CaseStatusMaster · CourtID: Foreign Key → Court · IncidentFromDate: DateTime · IncidentToDate: DateTime · InfoReceivedPSDate: DateTime · latitude: Double · longitude: Double · BriefFacts: Text · DistrictID: Foreign Key → District |
| `ComplainantDetails` | ComplainantID: Int (Is Unique) · CaseMasterID: Foreign Key → CaseMaster · ComplainantName: Var Char(150) · AgeYear: Int · OccupationID: Foreign Key → OccupationMaster · ReligionID: Foreign Key → ReligionMaster · CasteID: Foreign Key → CasteMaster · GenderID: Var Char(5) |
| `Victim` | VictimMasterID: Int (Is Unique) · CaseMasterID: Foreign Key → CaseMaster · VictimName: Var Char(150) · AgeYear: Int · GenderID: Var Char(5) · VictimPolice: Boolean |
| `Accused` | AccusedMasterID: Int (Is Unique) · CaseMasterID: Foreign Key → CaseMaster · AccusedName: Var Char(150) · AgeYear: Int · GenderID: Var Char(5) · PersonID: Var Char(10) · _pool_id: Int |
| `ActSectionAssociation` | CaseMasterID: Foreign Key → CaseMaster · ActID: Var Char(20) · SectionID: Var Char(20) · ActOrderID: Int · SectionOrderID: Int |
| `ArrestSurrender` | ArrestSurrenderID: Int (Is Unique) · CaseMasterID: Foreign Key → CaseMaster · ArrestSurrenderTypeID: Int · ArrestSurrenderDate: DateTime · ArrestSurrenderStateId: Foreign Key → State · ArrestSurrenderDistrictId: Foreign Key → District · PoliceStationID: Foreign Key → Unit · IOID: Foreign Key → Employee · CourtID: Foreign Key → Court · AccusedMasterID: Foreign Key → Accused · IsAccused: Boolean · IsComplainantAccused: Boolean |
| `ChargesheetDetails` | CSID: Int (Is Unique) · CaseMasterID: Foreign Key → CaseMaster · csdate: DateTime · cstype: Var Char(5) · PolicePersonID: Foreign Key → Employee |

**Note on `_pool_id` in Accused:** this column isn't in the official ER doc — it's our
proxy for cross-case identity resolution (a real system would use Zia-based fuzzy
matching on name/age/biometrics, since `AccusedMasterID` is scoped per-case). Flag this
to judges as a known simplification, not schema drift.

## Next: bulk-loading data
Once tables exist, run `catalyst_bulk_load.py` (companion script) to push each CSV via
Stratus + a Data Store bulk-write job — no manual row-by-row entry needed.
