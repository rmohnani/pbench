import React, { useState, useEffect } from "react";
import {useDispatch} from 'react-redux'
import "./index.css";
import {
  ToggleGroup,
  ToggleGroupItem,
  Page,
  Masthead,
  MastheadToggle,
  PageSidebar,
  PageToggleButton,
  PageSection,
  PageSectionVariants,
} from "@patternfly/react-core";
import {
  TableComposable,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from "@patternfly/react-table";
import axios from "axios";
import BarsIcon from "@patternfly/react-icons/dist/js/icons/bars-icon";
import SearchBox from "../SearchComponent";
import DatePickerWidget from "../DatePickerComponent";
import Heading from "../HeadingComponent";
import PathBreadCrumb from "../BreadCrumbComponent";
import AlertMessage from "../AlertComponent";
import NavItems from "../NavbarComponent";
import EmptyTable from "../EmptyStateComponent";
import moment from "moment";
import { fetchPublicDatasets } from "../../../actions/fetchPublicDatasets";
let startDate = moment(new Date(1990, 10, 4)).format("YYYY/MM/DD");
let endDate = moment(new Date(2040, 10, 4)).format("YYYY/MM/DD");
let controllerName = "";
let dataArray = [];
export const TableWithFavorite = () => {
  const columnNames = {
    controller: "Controller",
    name: "Name",
    creationDate: "Created On",
  };
  const [activeSortIndex, setActiveSortIndex] = useState(null);
  const [activeSortDirection, setActiveSortDirection] = useState(null);
  const [favoriteRepoNames, setFavoriteRepoNames] = useState([]);
  const [publicData, setPublicData] = useState([]);
  const [isSelected, setIsSelected] = useState("firstButton");
  const [isNavOpen, setIsNavOpen] = useState(false);
  const dispatch=useDispatch();
  useEffect(() => {
     dispatch(fetchPublicDatasets()).then((res) => {
        dataArray = res.data;
        setPublicData(res.data);
        setFavoriteRepoNames(JSON.parse(localStorage.getItem("favControllers")))
      })
      .catch((err) => {
        console.log(err);
      });
  }, []);
  const markRepoFavorited = (repo, isFavoriting = true) =>{
   const otherFavorites = favoriteRepoNames.filter((r) => r.name !== repo.name);
      if (isFavoriting) saveFavorites([...otherFavorites, repo]);
      else saveFavorites(otherFavorites);
      const newFavorite= isFavoriting ? [...otherFavorites, repo] : otherFavorites;
      setFavoriteRepoNames(newFavorite);
  }
    // setFavoriteRepoNames((prevFavorites) => {
    //   const otherFavorites = prevFavorites.filter((r) => r.name !== repo.name);
    //   if (isFavoriting) saveFavorites([...otherFavorites, repo]);
    //   else saveFavorites(otherFavorites);
    //   return isFavoriting ? [...otherFavorites, repo] : otherFavorites;
    // }

  const onNavToggle = () => {
    setIsNavOpen(!isNavOpen);
  };
  const isRepoFavorited = (repo) => {
    for (let i = 0; i < favoriteRepoNames.length; i++) {
      if (
        repo.name === favoriteRepoNames[i].name &&
        repo.controller === favoriteRepoNames[i].controller &&
        repo.metadata["dataset.created"] ===
          favoriteRepoNames[i].metadata["dataset.created"]
      )
        return true;
    }
    return false;
  };
  const getSortableRowValues = (publicData) => {
    const { controller, name } = publicData;
    const creationDate = publicData.metadata["dataset.created"];
    return [controller, name, creationDate];
  };
  let sortedRepositories = publicData;
  if (activeSortIndex !== null) {
    sortedRepositories = publicData.sort((a, b) => {
      const aValue = getSortableRowValues(a)[activeSortIndex];
      const bValue = getSortableRowValues(b)[activeSortIndex];
      if (aValue === bValue) {
        return 0;
      }
      if (activeSortDirection === "asc") {
        return aValue > bValue ? 1 : -1;
      } else {
        return bValue > aValue ? 1 : -1;
      }
    });
  }
  const getSortParams = (columnIndex) => ({
    isFavorites: columnIndex === 3,
    sortBy: {
      index: activeSortIndex,
      direction: activeSortDirection,
    },
    onSort: (_event, index, direction) => {
      setActiveSortIndex(index);
      setActiveSortDirection(direction);
    },
    columnIndex,
  });
  const handleButtonClick = (_isSelected, event) => {
    const id = event.currentTarget.id;
    setIsSelected(id);
  };
  const setControllerName = (controllerNameValue) => {
    controllerName = controllerNameValue;
  };
  const setDateRange = (startDateValue, endDateValue) => {
    startDate = startDateValue;
    endDate = endDateValue;
  };
  const saveFavorites = (fav) => {
    localStorage.setItem("favControllers", JSON.stringify(fav));
  };
  const Sidebar = (
    <PageSidebar
      nav={<NavItems />}
      className="sidebar"
      isNavOpen={isNavOpen}
    />
  );
  const NavbarDrawer = () => {
    return (
      <Masthead id="basic">
        <MastheadToggle>
          <PageToggleButton isNavOpen={isNavOpen} onNavToggle={onNavToggle}>
            <BarsIcon />
          </PageToggleButton>
        </MastheadToggle>
      </Masthead>
    );
  };
  const selectedArray =
    isSelected === "firstButton" ? publicData : favoriteRepoNames;
  return (
    <>
      <Page header={<NavbarDrawer />} sidebar={Sidebar}>
        <AlertMessage
          message="Want to see only metric relevant to you?"
          link="Login to create an account"
        />
        <PageSection variant={PageSectionVariants.light}>
          <PathBreadCrumb pathList={["Dashboard", "Components"]} />
          <Heading headingTitle="Controllers"></Heading>
          <div className="filterContainer">
            <SearchBox
              dataArray={dataArray}
              setPublicData={setPublicData}
              startDate={startDate}
              endDate={endDate}
              setControllerName={setControllerName}
            />
            <DatePickerWidget
              dataArray={dataArray}
              setPublicData={setPublicData}
              controllerName={controllerName}
              setDateRange={setDateRange}
            />
          </div>
          <ToggleGroup aria-label="Available options with Single Selectable">
            <ToggleGroupItem
              text={`All Controllers(${publicData.length})`}
              buttonId="firstButton"
              isSelected={isSelected === "firstButton"}
              onChange={handleButtonClick}
              className="controllerListButton"
            />
            <ToggleGroupItem
              text={`Favorites(${favoriteRepoNames.length})`}
              buttonId="secondButton"
              isSelected={isSelected === "secondButton"}
              onChange={handleButtonClick}
              className="favoriteListButton"
            />
          </ToggleGroup>
          <TableComposable aria-label="Favoritable table" variant="compact">
            <Thead>
              <Tr>
                <Th sort={getSortParams(0)}>{columnNames.controller}</Th>
                <Th sort={getSortParams(1)}>{columnNames.name}</Th>
                <Th sort={getSortParams(2)}>{columnNames.creationDate}</Th>
                <Th sort={getSortParams(3)}></Th>
              </Tr>
            </Thead>
            <Tbody>
              {selectedArray.length > 0 ? (
                selectedArray.map((repo, rowIndex) => (
                  <Tr key={rowIndex}>
                    <Td dataLabel={columnNames.controller}>
                      <a href="#">{repo.controller}</a>
                    </Td>
                    <Td dataLabel={columnNames.name}>{repo.name}</Td>
                    <Td dataLabel={columnNames.creationDate}>
                      {repo.metadata["dataset.created"]}
                    </Td>
                    <Td
                      favorites={{
                        isFavorited: isRepoFavorited(repo),
                        onFavorite: (_event, isFavoriting) => {
                          markRepoFavorited(repo, isFavoriting);
                        },
                        rowIndex,
                      }}
                    />
                  </Tr>
                ))
              ) : (
                <Td colSpan={8}>
                  <EmptyTable />
                </Td>
              )}
            </Tbody>
          </TableComposable>
        </PageSection>
      </Page>
    </>
  );
};
