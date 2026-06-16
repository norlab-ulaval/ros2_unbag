cmake_minimum_required(VERSION 3.16)

file(READ "${CMAKE_CURRENT_SOURCE_DIR}/package.xml" PACKAGE_XML_CONTENT)
string(REGEX MATCH "<version>([^<]+)</version>" _PACKAGE_VERSION_MATCH "${PACKAGE_XML_CONTENT}")
if(NOT _PACKAGE_VERSION_MATCH)
  message(FATAL_ERROR "Could not determine project version from package.xml")
endif()

project(ros2_unbag VERSION "${CMAKE_MATCH_1}")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_package(Qt5 REQUIRED COMPONENTS Core Widgets Svg)

ament_python_install_package(${PROJECT_NAME})
ament_get_python_install_dir(PYTHON_INSTALL_DIR)

set(ROS2_UNBAG_EGG_INFO_DIR "${CMAKE_CURRENT_BINARY_DIR}/python_metadata/ros2_unbag.egg-info")
set(ROS2_UNBAG_INSTALL_EGG_INFO_DIR
  "${PYTHON_INSTALL_DIR}/ros2_unbag-${PROJECT_VERSION}-py${Python3_VERSION_MAJOR}.${Python3_VERSION_MINOR}.egg-info"
)
add_custom_command(
  OUTPUT "${ROS2_UNBAG_EGG_INFO_DIR}/PKG-INFO"
  COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_CURRENT_BINARY_DIR}/python_metadata"
  COMMAND ${Python3_EXECUTABLE} setup.py egg_info --egg-base "${CMAKE_CURRENT_BINARY_DIR}/python_metadata"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  DEPENDS
    setup.py
    package.xml
    ros2_unbag/export.py
  COMMENT "Generating ros2_unbag egg-info metadata"
)
add_custom_target(ros2_unbag_python_metadata ALL
  DEPENDS "${ROS2_UNBAG_EGG_INFO_DIR}/PKG-INFO"
)

add_executable(ros2_unbag_gui
  src/main.cpp
  src/bridge_client.cpp
  src/main_window.cpp
  src/processor_chain_widget.cpp
  qt_resources/resources.qrc
)

target_include_directories(ros2_unbag_gui PRIVATE src)
target_link_libraries(ros2_unbag_gui PRIVATE Qt5::Core Qt5::Widgets Qt5::Svg)

install(TARGETS ros2_unbag_gui
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES
  package.xml
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY
  "${ROS2_UNBAG_EGG_INFO_DIR}/"
  DESTINATION "${ROS2_UNBAG_INSTALL_EGG_INFO_DIR}"
)

install(FILES
  resource/ros2_unbag
  DESTINATION share/ament_index/resource_index/packages
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_bridge tests/test_bridge.py)
  ament_add_pytest_test(test_pointcloud_exports tests/test_pointcloud_exports.py)
endif()

ament_package()
